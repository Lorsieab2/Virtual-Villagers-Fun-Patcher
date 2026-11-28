"""Heathen Tribe Expansion and Evolution (New Believers, v1.35.101): the row itself (workstream W-D).

docs/heathen-tribe-expansion-decisions.md: one row, vv5_heathen_tribe_evolution, off in Default Patches and Select
All, on in Owner's Defaults.  It ships VVFP Heathen Aging.dll, VVFP Heathen Life.dll and VVFP Heathen Mausoleum.dll
and the flag "VVFP Heathen Tribe Evolution.txt"; it folds Heathen Tribe Ages, Dies and Has Children, All Heathens Leave
Skeletons and Heathens can be selected in Island Events/Heathen-Exclusive Events (a saved selection or a command line
naming any of them gets the new row); its Settings window holds the two sliders, the show-action percent and Keep every
new Heathen blue, written at each patch beside the companions.  The companions' own behaviour is proven by
tests/test_vv5_heathen_evolution.py, tests/test_vv5_heathen_life.py, tests/test_vv5_heathen_mausoleum.py and
tests/test_vv5_heathen_evo_logs.py; the Settings window's widgets by tests/test_gui_patch_settings_windows.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import patcher_files  # noqa: E402
import vv_fun_patcher as vfp  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

ROW = "vv5_heathen_tribe_evolution"
FOLDED = ("vv5_heathen_tribe_ages", "vv5_all_heathens_leave_skeletons", "vv5_heathens_in_island_events")
FLAG = "VVFP Heathen Tribe Evolution.txt"
DLLS = {"VVFP Heathen Aging.dll": "heathen_aging", "VVFP Heathen Life.dll": "heathen_life",
        "VVFP Heathen Mausoleum.dll": "heathen_mausoleum"}
STOCK_EXE = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"


def record(row_id: str = ROW) -> dict:
    return json.loads((ROOT / "data" / f"{row_id}_feature.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class TheRow(unittest.TestCase):
    def test_registered_with_its_companions_pinned(self):
        row = record()
        self.assertEqual((row["id"], row["name"], row["game_id"]),
                         (ROW, "Heathen Tribe Expansion and Evolution", "vv5"))
        self.assertIn(ROW, {p.id for p in vfp.load_public_fun_patches()})
        files = {c["destination"]: c for c in row["companion_files"]}
        self.assertEqual(sorted(files), sorted(list(DLLS) + [FLAG]))
        for dll, folder in DLLS.items():
            with self.subTest(dll):
                source = ROOT / "assets" / folder / dll
                self.assertEqual(files[dll]["source"], f"assets/{folder}/{dll}")
                self.assertEqual(files[dll]["sha256"], sha(source), "pinned at its final build")
        self.assertEqual(files[FLAG]["sha256"], sha(ROOT / "assets" / "heathen_aging" / FLAG))
        self.assertIn(FLAG, patcher_files.PATCHER_READS)
        for name in (vfp.HEATHEN_BIRTHS_FILE, vfp.HEATHEN_ARRIVALS_FILE, vfp.HEATHEN_OPTIONS_FILE):
            self.assertIn(name, patcher_files.PATCHER_SETTINGS)
        self.assertEqual(row["conflicts"], [])
        self.assertEqual(row["dependencies"], [])
        self.assertIn("vv5_story_cheat_upgrades", [n["id"] for n in row["needs_on"]])

    def test_the_flag_names_the_row_and_matches_the_header(self):
        text = (ROOT / "assets" / "heathen_aging" / FLAG).read_bytes()
        self.assertTrue(text.startswith(b'Virtual Villagers Fun Patcher: "Heathen Tribe Expansion and Evolution"'))
        self.assertNotIn(b"\r", text)
        header = (ROOT / "native" / "shared" / "heathen_evo.h").read_text(encoding="utf-8")
        self.assertIn(f'#define HE_FLAG_ROW "{FLAG}"', header)
        self.assertIn(f'#define HE_FILE_BIRTHS "{vfp.HEATHEN_BIRTHS_FILE}"', header)
        self.assertIn(f'#define HE_FILE_ARRIVALS "{vfp.HEATHEN_ARRIVALS_FILE}"', header)
        self.assertIn(f'#define HE_FILE_OPTIONS "{vfp.HEATHEN_OPTIONS_FILE}"', header)

    def test_the_row_text_warns_in_bold_and_names_what_it_folds(self):
        text = record()["description"]
        self.assertIn("**A growing camp makes The Last Heathen harder to reach, or impossible", text)
        for name in ("Heathen Tribe Ages, Dies and Has Children", "All Heathens Leave Skeletons",
                     "Heathens can be selected in Island Events/Heathen-Exclusive Events"):
            self.assertIn(name, text)
        # the facilities are each named (decision 10)
        for place in ("pools", "Believer Idol", "science lab", "farm plots", "Love Shack", "Clothing Hut", "mud hut"):
            self.assertIn(place, text)
        self.assertIn("**Needs Story / Cheat Upgrades", text)

    def test_documented_everywhere(self):
        row = record()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"- Patch ID: `{ROW}`", readme)
        self.assertIn(row["description"], readme)
        news = readme[readme.index("## What's new in v1.35.101"):readme.index("## What's new in v1.35.100")]
        self.assertIn("**Heathen Tribe Expansion and Evolution**", news)
        self.assertIn("**A growing camp makes The Last Heathen harder to reach, or impossible.**", news)
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn("HEATHEN TRIBE EXPANSION AND EVOLUTION (NEW BELIEVERS)", how_to)
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn(f"#### Heathen Tribe Expansion and Evolution (`{ROW}`)", log)
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertEqual(len([e for e in guide["patches"] if ROW in e["ids"]]), 1)
        for key in ("heathen_tribe_births_multiplier", "heathen_arrivals_multiplier", "heathen_show_percent",
                    "heathen_keep_blue"):
            self.assertIn(key, guide["controls"])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"data/{ROW}_feature.json"', release)
        self.assertIn(f'"assets/heathen_aging/{FLAG}"', release)
        for dll, folder in DLLS.items():
            self.assertIn(f'"assets/{folder}/{dll}"', release)
        # the Settings window's words are translation rows (vvfp.gui/heathen_evolution.*)
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        english = {r["stem"]: r["english"] for r in rows["strings"]}
        for text in gui.HEATHEN_SETTINGS_TEXTS:
            self.assertIn(text, english.values())

    def test_the_folded_rows_are_gone(self):
        ids = {p.id for p in vfp.load_public_fun_patches()}
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for old in FOLDED:
            with self.subTest(old):
                self.assertNotIn(old, ids)
                self.assertFalse((ROOT / "data" / f"{old}_feature.json").exists())
                self.assertNotIn(f'"data/{old}_feature.json"', release)
                self.assertEqual(vfp.FOLDED_FUN_PATCH_IDS[old], ROW)


class Defaults(unittest.TestCase):
    def test_off_by_default_and_in_select_all_on_in_owners_defaults(self):
        self.assertFalse(gui.default_fun_patch_selection(ROW))
        self.assertFalse(gui.select_all_fun_patch_selection(ROW))
        self.assertTrue(gui.owners_default_fun_patch_selection(ROW))
        self.assertNotIn(ROW, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(ROW, gui.UNTICKING_CONFLICT_IDS)

    def test_the_former_villager_rows_stay_separate(self):
        ids = {p.id for p in vfp.load_public_fun_patches()}
        for kept in ("vv5_former_villagers_keep_aging", "vv5_former_villager_heathens_leave_skeletons"):
            self.assertIn(kept, ids)
            self.assertTrue(gui.owners_default_fun_patch_selection(kept))
            self.assertEqual(record(kept)["conflicts"], [], "the skeleton conflict is dropped")

    def test_the_settings_defaults(self):
        self.assertEqual(gui.saved_heathen_evolution({}), (1, 0, 25, False), "births 1x, no arrivals, 25%, masks mixed")
        self.assertEqual(vfp.HEATHEN_ARRIVALS_OWNERS_DEFAULT, 1, "Owner's Defaults: arrivals at 1x (decision 3)")


class Migration(unittest.TestCase):
    def test_a_saved_selection_naming_a_folded_row_ticks_the_new_row(self):
        for old in FOLDED:
            with self.subTest(old):
                self.assertEqual(gui.restored_fun_selection([old]), [ROW])
        self.assertEqual(gui.restored_fun_selection(list(FOLDED) + ["vv5_former_villager_heathens_leave_skeletons"]),
                         [ROW, "vv5_former_villager_heathens_leave_skeletons"], "once, in order")
        self.assertEqual(gui.restored_fun_selection(["vv5_puddles_by_the_lake", ROW]),
                         ["vv5_puddles_by_the_lake", ROW], "nothing else changes")

    def test_the_command_line_takes_an_old_id(self):
        parser = vfp._parser()
        for old in FOLDED:
            args = parser.parse_args(["dry-run", "x.exe", "--fun-patch", old])
            self.assertEqual(vfp.migrated_fun_patch_ids(args.fun_patch), [ROW])

    def test_the_folded_flags_are_removed_from_a_re_patched_folder(self):
        """The companions still honour the old flags; a folder patched before v1.35.101 keeps them unless a re-patch
        removes them, by their exact bytes (RETIRED_PATCHER_FILES)."""
        import build_heathen_aging_features as aging
        expected = {aging.FLAGS[aging.TRIBE_ID]: aging.flag_text(aging.TRIBE_ID),
                    aging.FLAGS[aging.BONES_ALL_ID]: aging.flag_text(aging.BONES_ALL_ID),
                    aging.EVENTS_FLAG: aging.flag_text(aging.EVENTS_ID)}
        retired = dict(vfp.RETIRED_PATCHER_FILES["vv5"])
        self.assertEqual(set(retired), set(expected))
        for name, text in expected.items():
            self.assertEqual(retired[name], hashlib.sha256(text).hexdigest().upper(), name)
        with tempfile.TemporaryDirectory() as folder:
            staging = Path(folder)
            files = staging / patcher_files.PATCHER_FILES_FOLDER
            files.mkdir()
            for name, text in expected.items():
                (files / name).write_bytes(text)
            (files / "VVFP Heathen Skeletons All.txt").write_bytes(b"edited by the player\n")
            build = next(b for b in vfp.load_builds() if b.id == "vv5")
            removed = vfp._remove_unselected_companions(staging, build, [])
            gone = {Path(item["path"]).name for item in removed}
            self.assertEqual(gone & set(expected), {aging.FLAGS[aging.TRIBE_ID], aging.EVENTS_FLAG})
            self.assertTrue((files / "VVFP Heathen Skeletons All.txt").exists(), "a changed file is left alone")


class Settings(unittest.TestCase):
    def tearDown(self):
        vfp.set_heathen_evolution(births=1, arrivals=0, show_percent=25, keep_blue=False)

    def test_saved_settings_are_kept_within_range(self):
        self.assertEqual(gui.saved_heathen_evolution({"heathen_tribe_births_multiplier": 0,
                                                      "heathen_arrivals_multiplier": 50,
                                                      "heathen_show_percent": 0, "heathen_keep_blue": "yes"}),
                         (0.1, 10, 25, False))
        self.assertEqual(gui.saved_heathen_evolution({"heathen_arrivals_multiplier": 0}), (1, 0, 25, False))
        self.assertEqual(gui.saved_heathen_evolution({"heathen_arrivals_multiplier": 2.5, "heathen_show_percent": 100,
                                                      "heathen_keep_blue": True}), (1, 2.5, 100, True))

    def test_out_of_range_numbers_are_refused(self):
        for kwargs in ({"births": 0}, {"births": 11}, {"arrivals": -1}, {"arrivals": 10.5}, {"show_percent": 0},
                       {"show_percent": 101}, {"show_percent": True}):
            with self.subTest(**kwargs), self.assertRaises(vfp.PatcherError):
                vfp.set_heathen_evolution(**kwargs)

    def test_the_files_written_beside_the_companions(self):
        row = next(p for p in vfp.load_public_fun_patches() if p.id == ROW)
        vfp.set_heathen_evolution(births=2.5, arrivals=0, show_percent=40, keep_blue=True)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            vfp._write_heathen_evolution_choices(out, [row])
            files = out / patcher_files.PATCHER_FILES_FOLDER
            self.assertEqual((files / "VVFP Heathen Tribe Births.txt").read_bytes(), b"2.5\n")
            self.assertEqual((files / "VVFP Heathen Arrivals.txt").read_bytes(), b"0\n", "0 = no arrivals")
            options = (files / "VVFP Heathen Options.txt").read_text(encoding="ascii")
            self.assertIn("show_percent=40\n", options)
            self.assertIn("mask_orange_percent=0\nmask_red_percent=0\n", options)
        vfp.set_heathen_evolution(arrivals=1, keep_blue=False)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            vfp._write_heathen_evolution_choices(out, [row])
            files = out / patcher_files.PATCHER_FILES_FOLDER
            self.assertEqual((files / "VVFP Heathen Arrivals.txt").read_bytes(), b"1\n")
            self.assertNotIn("mask_", (files / "VVFP Heathen Options.txt").read_text(encoding="ascii"),
                             "the owner's 90/7/3 stand (heathen_evo.h defaults)")
        with tempfile.TemporaryDirectory() as folder:
            vfp._write_heathen_evolution_choices(Path(folder), [])
            self.assertEqual(list(Path(folder).iterdir()), [], "nothing without the row")

    def test_the_options_file_reads_as_the_companions_read_it(self):
        """heathen_evo.h he_option: "key=value" lines, '#' comments; the patcher's file holds only known keys."""
        vfp.set_heathen_evolution(show_percent=7, keep_blue=True)
        text = vfp.heathen_options_text()
        values = dict(line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#"))
        self.assertEqual(values, {"show_percent": "7", "busyness": "2", "mask_orange_percent": "0",
                                  "mask_red_percent": "0"})
        header = (ROOT / "native" / "shared" / "heathen_evo.h").read_text(encoding="utf-8")
        for key in ("show_percent", "mask_orange_percent", "mask_red_percent"):
            self.assertIn(f'"{key}"', header)

    def test_the_patch_log_names_the_settings_only_with_the_row(self):
        row = next(p for p in vfp.load_public_fun_patches() if p.id == ROW)
        self.assertIsNone(vfp._heathen_evolution_in([]))
        self.assertEqual(vfp._heathen_evolution_in([row]),
                         {"heathen_tribe_births_multiplier": 1, "heathen_arrivals_multiplier": 0,
                          "heathen_show_percent": 25, "heathen_keep_blue": False,
                          "heathen_busyness": "normal"})

    def test_the_settings_window_is_registered(self):
        self.assertEqual(gui.PATCH_SETTINGS_ROWS["heathen_tribe_evolution"][0], "_fill_heathen_evolution_settings")
        self.assertTrue(callable(getattr(gui.App, "_fill_heathen_evolution_settings")))


class Shipping(unittest.TestCase):
    def test_the_companions_ship_only_with_their_rows(self):
        expect = {"VVFP Heathen Aging.dll": {ROW, "vv5_former_villagers_keep_aging"},
                  "VVFP Heathen Life.dll": {ROW},
                  "VVFP Heathen Mausoleum.dll": {ROW, "vv5_former_villager_heathens_leave_skeletons"},
                  FLAG: {ROW}}
        found = {name: set() for name in expect}
        for path in (ROOT / "data").glob("*_feature.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            for item in row.get("companion_files", []):
                if item.get("destination") in found:
                    found[item["destination"]].add(row["id"])
        self.assertEqual(found, expect)

    def test_the_startup_bits(self):
        third = vfp.STARTUP_LOADER_COMPANIONS_3
        self.assertEqual(third.index("VVFP Heathen Aging.dll"), 15)
        self.assertEqual(third.index("VVFP Window Restore.dll"), 20)
        self.assertEqual(third.index("VVFP Heathen Life.dll"), 21)
        self.assertEqual(third.index("VVFP Heathen Mausoleum.dll"), 22)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        listed = [line.strip()[1:-2] for line in header.splitlines() if line.strip().startswith('"VVFP ')]
        self.assertEqual(tuple(listed), third, "the header and the patcher list the same names in the same order")
        self.assertLessEqual(len(third), 32)
        rows = {p.id: p for p in vfp.load_public_fun_patches()}
        self.assertEqual(vfp._startup_loader_mask_3([rows[ROW]]), (1 << 15) | (1 << 21) | (1 << 22))
        self.assertEqual(vfp._startup_loader_mask_3([rows["vv5_former_villager_heathens_leave_skeletons"]]), 1 << 22)
        more = json.loads((ROOT / "data" / "more_companions_companion.json").read_text(encoding="utf-8"))
        self.assertEqual(more["sha256"], sha(ROOT / "assets" / "more_companions" / "VVFP More Companions.dll"))

    def test_the_runtime_detours_hold_the_stock_bytes(self):
        if not STOCK_EXE.is_file():
            self.skipTest("the stock New Believers executable is not in inputs/")
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(STOCK_EXE), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        rows = [record(), record("vv5_former_villager_heathens_leave_skeletons")]
        for row in rows:
            for detour in row["runtime_detours"]:
                va = int(detour["va"], 16)
                stock = bytes.fromhex(detour["stock_bytes"])
                with self.subTest(row=row["id"], va=detour["va"]):
                    self.assertEqual(pe.get_data(va - base, len(stock)), stock)
        sites = {d["va"] for d in record()["runtime_detours"]}
        for va in ("0x470077", "0x472CB7", "0x46F0BA", "0x473FA9", "0x414DB0", "0x4150D7"):
            self.assertIn(va, sites, "the Aging, Life, Mausoleum and Story sites are all declared")

    def test_the_owed_exports_exist(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        wanted = {
            "assets/story_upgrades/VVFP Story Upgrades.dll": "VvfpStorySetCustomTitle",
            "assets/parentage/VVFP Parentage Export.dll": "WriteParentageHeathenCouple",
            "assets/cause_of_death/VVFP Cause of Death.dll": "VvfpCauseHeathenRole",
            "assets/heathen_life/VVFP Heathen Life.dll": "VvfpHeathenLifeUnit",
            "assets/heathen_mausoleum/VVFP Heathen Mausoleum.dll": "VvfpHeathenMausoleumVillageReset",
        }
        for relative, export in wanted.items():
            path = ROOT / relative
            names = {e.name.decode() for e in pefile.PE(str(path)).DIRECTORY_ENTRY_EXPORT.symbols if e.name}
            with self.subTest(export):
                self.assertIn(export, names)


class CopySlot(unittest.TestCase):
    def test_the_shrine_and_the_couples_files_are_retagged(self):
        import vv_copy_slot
        self.assertEqual(vv_copy_slot._SLOT_FIELD[b"VHM1"], 16)
        self.assertEqual(vv_copy_slot._SLOT_FIELD[b"VHC1"], 16)


class GameMechanics(unittest.TestCase):
    def test_the_faith_page_reads_the_village_s_own_settings(self):
        import vv_game_mechanics_faith_vv5 as faith
        lines = []

        def add(text, *args, **kwargs):
            lines.append(text)

        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / "Virtual Villagers - New Believers.exe"
            files = Path(folder) / patcher_files.PATCHER_FILES_FOLDER
            files.mkdir()
            (files / "VVFP Heathen Tribe Births.txt").write_text("2\n", encoding="ascii")
            (files / "VVFP Heathen Arrivals.txt").write_text("0\n", encoding="ascii")
            (files / "VVFP Heathen Options.txt").write_text("show_percent=40\n", encoding="ascii")
            faith._heathen_evolution_facts(add, types.SimpleNamespace(exe=exe), "in this game")
        text = "\n".join(lines)
        self.assertIn("Births (at 2x)", text)
        self.assertIn("2 times as often", text)
        self.assertIn("New arrivals: none", text)
        self.assertIn("Show actions (40%", text)
        self.assertIn("Shrine to the Ancestors", text)
        self.assertIn("never below 21", text)
        lines.clear()
        faith._heathen_evolution_facts(add, types.SimpleNamespace(exe=None), "in this game")
        text = "\n".join(lines)
        self.assertIn("Births (set by its slider)", text)
        self.assertIn("New arrivals (set by its slider)", text)


if __name__ == "__main__":
    unittest.main()
