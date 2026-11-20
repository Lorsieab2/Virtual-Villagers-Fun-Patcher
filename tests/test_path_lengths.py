"""No "Path too long" (the owner, 2026-11-19, before v1.35.97).

Windows Explorer, the games and many tools stop at MAX_PATH (260 characters): copying or unzipping a patched game
failed on "...\\Virtual Villagers - New Believers - Modded 256\\Virtual Villagers Fun Patcher Files\\Island Event
Collection\\vv5_the_guardians_disagreement.cieg".  The patcher's own top folder keeps its full name (the owner: "THE
PATCHER FOLDER SHOULD SAY THE FULL NAME"); the added files under it have short names instead: the collection's
folder is "Events", its events "<number>.cieg" (numbers that never change: data/event_collection/file_numbers.tsv),
its manifests "<group>.lst" and its living packs "<group>.pak".  Pinned here, in all five games:

* every file a patch installs, relative to the game folder, is at most INSTALLED_RELATIVE_BUDGET characters (the
  Player Events reference documents, which a player opens and which keep their names, are listed by name: no other
  file may pass it);
* every entry of the release zip is at most ZIP_ENTRY_BUDGET characters;
* the numbering: one number per id, never two ids on one number, every shipped event and manifest row on its number;
* a deep output folder (200 characters) gives the patcher's clear message, never another exception, and a folder of
  150 characters now patches every game with every patch;
* Player Events writes into a game folder deeper than MAX_PATH;
* a re-patch removes the collection's older long-named folder ("Island Event Collection") and keeps anything else.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import patcher_files  # noqa: E402
import vv_fun_patcher as vfp  # noqa: E402
import vv_player_events as pe  # noqa: E402
import build_event_collection_features as build  # noqa: E402

FOLDER = patcher_files.PATCHER_FILES_FOLDER
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")

# Documents a player opens (Player Events' shipped references, copied into "<patcher folder>\\Player Events"): they
# keep their readable names (the owner, 2026-11-19: only the added data files are shortened).  Listed so no other
# file can pass the budget unnoticed.
KNOWN_LONG_DOCUMENTS = {
    f"{FOLDER}/{pe.INSTALLED_FOLDER}/{name}" for name in (pe.PROMPT_NAME,) + pe.OWNER_FILES
    if len(f"{FOLDER}/{pe.INSTALLED_FOLDER}/{name}") > patcher_files.INSTALLED_RELATIVE_BUDGET
}


def feature_records():
    for path in sorted((ROOT / "data").glob("*_feature.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(raw, dict) and raw.get("companion_files"):
            yield path.name, raw


def installed_paths() -> dict[str, str]:
    """{relative path in the game folder: where it comes from} for every file a patch can install."""
    out: dict[str, str] = {}
    for name, raw in feature_records():
        for item in raw["companion_files"]:
            out[patcher_files.installed_relative_path(item["destination"]).as_posix()] = name
    for relative in patcher_files.RUNTIME_GAME_FILES:
        out[relative] = "a companion at run time"
    for name in patcher_files.PATCHER_SETTINGS:
        out[f"{FOLDER}/{name}"] = "a slider's setting"
    for relative in (patcher_files.TRANSPARENCY_RELATIVE_PATH, patcher_files.INSTALLED_PATCHES_RELATIVE_PATH,
                     patcher_files.patch_log_relative_path()):
        out[relative.as_posix()] = "the patcher's report"
    # Player Events: the longest names it can write (a group of GROUP_NAME_MAX, a four-digit event number), its
    # report, and the references a player opens.
    group = "x" * pe.GROUP_NAME_MAX
    for leaf in (f"{group}{pe.MANIFEST_EXT}", f"{group}.pcb", f"{pe.PLAYER_FILE_PREFIX}9999.cieg"):
        out[f"{FOLDER}/{pe.COLLECTION_FOLDER}/{leaf}"] = "Player Events"
    for leaf in ("Player Events Report.txt", pe.PROMPT_NAME) + pe.OWNER_FILES:
        out[f"{FOLDER}/{pe.INSTALLED_FOLDER}/{leaf}"] = "Player Events"
    out[f"{FOLDER}/{build.FOLDER}/Problems.txt"] = "Story Upgrades at run time"
    return out


class TheBudgets(unittest.TestCase):
    def test_every_installed_path_is_within_the_budget(self):
        paths = installed_paths()
        self.assertGreater(len(paths), 4000)
        over = {p for p in paths if patcher_files.windows_length(p) > patcher_files.INSTALLED_RELATIVE_BUDGET}
        self.assertEqual(over, KNOWN_LONG_DOCUMENTS,
                         "\n".join(f"{patcher_files.windows_length(p)} {p} ({paths.get(p)})"
                                   for p in sorted(over ^ KNOWN_LONG_DOCUMENTS, key=len, reverse=True)))

    def test_the_collection_uses_short_names_in_every_game(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                raw = json.loads((ROOT / "data" / f"vv{game}_isola_grand_event_collection_feature.json")
                                 .read_text(encoding="utf-8"))
                for item in raw["companion_files"]:
                    folder, leaf = item["destination"].split("/")
                    self.assertEqual(folder, "Events")
                    self.assertRegex(leaf, r"^(?:\d+\.cieg|[a-z0-9_]{1,24}\.(?:lst|pak)|Credits\.txt)$")
                    self.assertNotIn(patcher_files.LEGACY_COLLECTION_FOLDER, item["destination"])

    def test_every_release_zip_entry_is_within_the_budget(self):
        import build_release
        over = [e for e in build_release.FILES if len(e) > patcher_files.ZIP_ENTRY_BUDGET]
        self.assertEqual(over, [])
        self.assertLessEqual(len(build_release.NAME), 60)          # the zip's own name stays short too

    def test_the_patchers_own_folder_keeps_its_full_name(self):
        self.assertEqual(FOLDER, "Virtual Villagers Fun Patcher Files")
        text = (ROOT / "native" / "shared" / "patcher_files.h").read_text(encoding="utf-8")
        self.assertIn('"Virtual Villagers Fun Patcher Files"', text)


class TheNumbers(unittest.TestCase):
    """The owner, 2026-11-19: "just number the added events" -- numbers that never change between versions."""

    def test_the_table_is_one_to_one_and_has_every_shipped_event(self):
        table = build.read_numbers()
        self.assertEqual(len(set(table.values())), len(table), "a number given twice")
        self.assertEqual(min(table.values()), 1)
        shipped = {p.stem for p in (ROOT / "assets" / "event_collection").glob("*.cieg")}
        self.assertEqual(shipped - set(table), set(), "a shipped event without a number")
        # new ids are appended after every existing number (file_numbers)
        grown = build.file_numbers(list(table) + ["zz_a_new_event"])
        self.assertEqual(grown["zz_a_new_event"], max(table.values()) + 1)
        self.assertEqual({k: v for k, v in grown.items() if k in table}, table)

    def test_every_row_and_file_is_on_its_number(self):
        table = build.read_numbers()
        for game in range(1, 6):
            raw = json.loads((ROOT / "data" / f"vv{game}_isola_grand_event_collection_feature.json")
                             .read_text(encoding="utf-8"))
            for item in raw["companion_files"]:
                if item["destination"].endswith(".cieg"):
                    ident = Path(item["source"]).stem
                    self.assertEqual(item["destination"], f"Events/{table[ident]}.cieg", ident)
            for path in sorted((ROOT / "assets" / "event_collection" / f"vv{game}").glob("manifest-*.txt")):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    fields = line.split("\t") + [""] * 11
                    if (ROOT / "assets" / "event_collection" / f"{fields[0]}.cieg").is_file():
                        self.assertEqual(fields[10], str(table[fields[0]]), (path.name, fields[0]))
                    else:                      # a living seed's row: its event is in the pack, no file of its own
                        self.assertEqual(fields[10], "", (path.name, fields[0]))


def short_base(case: unittest.TestCase) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix="vp")
    case.addCleanup(tmp.cleanup)
    return Path(os.path.abspath(tmp.name))


class DeepFolders(unittest.TestCase):
    def features(self, game: str):
        return [f for f in vfp.load_fun_patches() if f.game_id == game]

    def test_a_200_character_folder_gets_the_clear_message(self):
        base = short_base(self)
        for game in GAMES:
            with self.subTest(game=game):
                out = base / ("d" * (200 - len(str(base)) - 1))
                self.assertEqual(len(str(out)), 200)
                with self.assertRaises(vfp.PatcherError) as raised:
                    vfp._require_patcher_files_path_fits(out, self.features(game), "g.exe")
                message = str(raised.exception)
                self.assertIn("too long", message)
                self.assertIn("Nothing was written", message)
                self.assertIn("Choose an output folder", message)

    def test_a_150_character_folder_fits_every_patch_of_every_game(self):
        base = short_base(self)
        out = base / ("d" * (150 - len(str(base)) - 1))
        for game in GAMES:
            with self.subTest(game=game):
                vfp._require_patcher_files_path_fits(out, self.features(game),
                                                     "Virtual Villagers - New Believers - Modded 256.exe")

    def test_player_events_write_past_max_path(self):
        base = short_base(self)
        root = base / "pe"
        src = pe.ensure_game_folder(1, root)
        sys.path.insert(0, str(ROOT / "tests"))
        from test_player_events import SIMPLE
        (src / "mine.txt").write_text(SIMPLE, encoding="utf-8")
        game = base / ("g" * 120) / ("h" * 100)
        patcher_files.long_path(game).mkdir(parents=True)
        report = pe.install(1, game, src, pe.Settings(), root)
        self.assertEqual(len(report.installed), 1)
        shown = game / FOLDER / pe.INSTALLED_FOLDER / pe.PROMPT_NAME
        self.assertGreater(len(str(shown)), patcher_files.MAX_PATH)
        self.assertTrue(patcher_files.long_path(shown).is_file())
        self.assertTrue(patcher_files.long_path(game / FOLDER / "Events" / "p1.cieg").is_file())


class TheOlderFolder(unittest.TestCase):
    def test_a_repatch_removes_the_older_long_named_folder(self):
        base = short_base(self)
        old = base / FOLDER / patcher_files.LEGACY_COLLECTION_FOLDER
        old.mkdir(parents=True)
        written = ["vv5_the_guardians_disagreement.cieg", "pl_mine_001.cieg", "manifest-an_age.txt", "manifest.txt",
                   "living-le_per.pak", "living.pak", "pieces-pl_x.pcb", "Credits.txt", "Problems.txt"]
        for name in written:
            (old / name).write_bytes(b"x")
        removed = vfp._remove_legacy_collection_folder(base)
        self.assertEqual(sorted(Path(r["path"]).name for r in removed), sorted(written))
        self.assertFalse(old.exists())
        # Anything else in it stays (and so does the folder).
        old.mkdir()
        (old / "a.cieg").write_bytes(b"x")
        (old / "my notes.docx").write_bytes(b"mine")
        removed = vfp._remove_legacy_collection_folder(base)
        self.assertEqual([Path(r["path"]).name for r in removed], ["a.cieg"])
        self.assertTrue((old / "my notes.docx").is_file())

    def test_an_overwrite_never_carries_the_older_folder_or_old_player_files_over(self):
        old = Path(FOLDER) / patcher_files.LEGACY_COLLECTION_FOLDER
        self.assertTrue(vfp._legacy_collection_relative(old / "vv5_the_guardians_disagreement.cieg"))
        self.assertFalse(vfp._legacy_collection_relative(Path(FOLDER) / "Events" / "12.cieg"))
        for name in ("p3.cieg", "pl_mine.lst", "pl_mine.pcb"):
            self.assertTrue(vfp._player_events_relative(Path(FOLDER) / "Events" / name), name)
        for name in ("12.cieg", "an_age.lst", "le_per.pak", "Credits.txt"):
            self.assertFalse(vfp._player_events_relative(Path(FOLDER) / "Events" / name), name)

    def test_its_long_names_never_refuse_a_folder(self):
        base = short_base(self)
        source = base / "s"
        old = source / FOLDER / patcher_files.LEGACY_COLLECTION_FOLDER
        old.mkdir(parents=True)
        (old / ("v" * 30 + ".cieg")).write_bytes(b"x")
        out = base / ("o" * (patcher_files.MAX_PATH - 1 - len(str(base)) - 1 - len(FOLDER) - 30))
        vfp._require_patcher_files_path_fits(out, [], "g.exe", source)


if __name__ == "__main__":
    unittest.main()
