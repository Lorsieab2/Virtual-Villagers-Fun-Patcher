"""Every file the patcher adds is in "Virtual Villagers Fun Patcher Files".

The owner (2026-10-04): "can we put all the patcher dlls and files into a
folder 'Virtual Villagers Fun Patcher Files' to clean up the game folders a
bit? all 5 games". So every companion DLL, VVFP Startup.dll, the images only
the companions read, the patch log and the transparency log go in that
folder beside the modified executable; the only exceptions are files the game
engine itself opens by its own path (src/patcher_files.py lists each, with
its reason). Pinned here:

* the rule itself: every catalog file is classified, DLLs and companion-read
  assets go in the folder, the in-place list is exactly the game-read files;
* the published layout, for every game with every public patch: the game
  folder gains only the modified executable, the folder and the documented
  in-place files, and the patch log and transparency log are in the folder;
* re-patching over a folder an older patcher made removes its LOOSE files
  (by the catalog's names; non-DLL files only when byte-identical), keeps the
  player's own, and leaves nothing twice -- and the mutation (no cleanup)
  keeps them;
* a source folder carrying loose copies is cleaned the same way;
* an output folder too deep for Windows to load the add-ons from is refused
  before anything is written, at exactly MAX_PATH;
* no shipped DLL can load a companion through the ANSI API or a bare name
  (import tables, sources), and the native path builder's own harness
  (Unicode folders, the buffer's edge, names that would leave the folder,
  real files and a real DLL in a Unicode folder).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import patcher_files  # noqa: E402
import vv_fun_patcher as vfp  # noqa: E402

FOLDER = patcher_files.PATCHER_FILES_FOLDER
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
STOCK_DIR = ROOT / "research" / "stock-executables"
POPULATION_256 = {"vv3_population_256", "vv4_population_256", "vv5_population_256"}
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")


@lru_cache(maxsize=None)
def build_of(game: str):
    return next(b for b in vfp.load_builds() if b.id == game)


def stock_path(game: str) -> Path:
    return STOCK_DIR / build_of(game).input_name


STOCK_PRESENT = all(stock_path(g).is_file() for g in GAMES)
STOCK_ABSENT = "the stock executables are not in this checkout (research/stock-executables)"


def replaces_game_files(feature) -> bool:
    """An asset swap: it replaces the game's own files, which a folder holding
    only the stock executable does not have (they stay in place anyway)."""
    return any(item.get("preimage_sha256") for item in feature.raw.get("companion_files", []))


def public_ids(game: str) -> list[str]:
    return [p.id for p in vfp.load_fun_patches()
            if p.game_id == game and not p.raw.get("catalog_hidden")
            and p.raw.get("catalog_enabled", True) and p.raw.get("enabled", True)
            and p.id not in POPULATION_256 and not replaces_game_files(p)]


def catalog_items(game: str | None = None):
    for feature in vfp._load_fun_patch_records():
        if game is not None and feature.raw.get("game_id") != game:
            continue
        for item in feature.raw.get("companion_files", []):
            yield feature, item


class TheRule(unittest.TestCase):

    def test_every_catalog_file_is_placed(self):
        destinations = {item["destination"] for _, item in catalog_items()}
        destinations.add(vfp.STARTUP_LOADER_DLL)
        for destination in sorted(destinations):
            with self.subTest(destination=destination):
                installed = vfp._safe_companion_destination(destination).as_posix()
                if destination.lower().endswith(".dll"):
                    self.assertEqual(installed, f"{FOLDER}/{destination.replace(chr(92), '/')}")
                elif patcher_files.stays_in_place(destination):
                    self.assertEqual(installed, destination.replace("\\", "/"))
                else:
                    self.assertTrue(installed.startswith(FOLDER + "/"), installed)

    def test_the_in_place_list_is_exactly_the_catalogs_game_read_files(self):
        """No stale entry, and no catalog file the game does not read left
        out of the folder."""
        catalog = {item["destination"].replace("\\", "/").casefold() for _, item in catalog_items()}
        in_place = {k.casefold() for k in patcher_files.GAME_READS_IN_PLACE}
        self.assertEqual(in_place - catalog, set())
        non_dll = {d for d in catalog if not d.endswith(".dll")}
        self.assertEqual(non_dll - in_place, {k.casefold() for k in patcher_files.PATCHER_READS})

    def test_an_unclassified_file_is_refused(self):
        with self.assertRaises(vfp.PatcherError):
            vfp._safe_companion_destination("Images/something_new.png")
        for unsafe in ("../x.dll", "C:/x.dll", "/x.dll", "a/../x.dll", ""):
            with self.subTest(unsafe=unsafe), self.assertRaises(vfp.PatcherError):
                vfp._safe_companion_destination(unsafe)

    def test_the_native_header_names_the_same_folder(self):
        header = (ROOT / "native" / "shared" / "patcher_files.h").read_text(encoding="utf-8")
        self.assertIn(f'#define VVFP_PATCHER_FILES_FOLDER "{FOLDER}"', header)
        self.assertEqual(vfp.STARTUP_LOADER_TAIL.decode("utf-16-le"),
                         FOLDER + "\\" + vfp.STARTUP_LOADER_DLL + "\0")

    def test_the_logs_are_in_the_folder(self):
        self.assertEqual(patcher_files.patch_log_relative_path("A - Modded.exe").as_posix(),
                         f"{FOLDER}/A - Modded.patch-log.json")
        self.assertEqual(patcher_files.TRANSPARENCY_RELATIVE_PATH.as_posix(),
                         f"{FOLDER}/VVFP Transparency Log.txt")


SHIPPING_SOURCES = (
    "native/vvfp_startup", "native/shared", "native/vv1_origins_icons", "native/vv2_origins_icons",
    "native/vv3_full_mastery_candidate", "native/vv4_origins_icons", "native/vv5_task9_origins",
    "native/parentage_export", "native/population_export", "native/statistics_export",
    "native/save_reset_export", "native/vvfp_cause_of_death", "native/vvfp_fix_huts",
    "native/vvfp_golden_mushroom", "native/vvfp_story_upgrades", "native/vv1_parentage",
    "native/vvfp_work_first", "native/vvfp_lesson_cap", "native/vvfp_healers_study",
    "native/vvfp_pathfinding", "native/vv1_number_keys", "native/vv1_sort_by", "native/vv1_watering_builds",
    "native/vvfp_storytelling",
)
# The executable's own name decides the game's save folder, and the games
# derive it with GetModuleFileNameA; these keep the ANSI call so the
# companions name the very folder the game saves in (only the name, which
# the patcher writes in ASCII, is used -- never the folder's path).
SAVE_FOLDER_BASENAME_FUNCTIONS = {
    "native/shared/save_folder.c": 1,
    "native/shared/paid_purchases.h": 1,   # the save folder for a bought, undelivered barrel
    "native/vv1_origins_icons/vv1_origins_icons.c": 2,
    "native/vv1_parentage/vv1_crosscheck.inc": 1,
    "native/vv1_parentage/vv1_parentage.c": 1,
    "native/vv2_origins_icons/vv2_origins_icons.c": 1,
    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c": 1,
    "native/vv4_origins_icons/vv4_origins_icons.c": 1,
    "native/vv5_task9_origins/vv5_task9_origins.c": 1,
}


class NoCompanionIsFoundByTheAnsiApiOrABareName(unittest.TestCase):

    def shipped_dlls(self):
        sources = {item["source"] for _, item in catalog_items()
                   if str(item["destination"]).lower().endswith(".dll")}
        sources.add(vfp.STARTUP_LOADER_COMPANION["source"])
        return sorted(ROOT / s for s in sources if (ROOT / s).is_file())

    def test_no_shipped_dll_imports_an_ansi_or_plain_loader(self):
        for path in self.shipped_dlls():
            with self.subTest(dll=path.name):
                pe = pefile.PE(data=path.read_bytes())
                names = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
                self.assertEqual(names & {"LoadLibraryA", "LoadLibraryW", "LoadLibraryExA"}, set())

    def sources(self):
        for folder in SHIPPING_SOURCES:
            for path in sorted((ROOT / folder).glob("*")):
                if path.suffix in (".c", ".h", ".inc") and "harness" not in path.name:
                    yield path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")

    def test_no_shipped_source_loads_by_a_bare_name_or_an_ansi_path(self):
        for name, text in self.sources():
            code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            with self.subTest(source=name):
                self.assertNotRegex(code, r"\bLoadLibraryA?\s*\(")
                self.assertNotRegex(code, r"\bLoadLibraryW\s*\(")
                calls = len(re.findall(r"\bGetModuleFileNameA\s*\(", code))
                self.assertEqual(calls, SAVE_FOLDER_BASENAME_FUNCTIONS.get(name, 0))

    def test_only_the_header_loads_a_companion(self):
        loads = [name for name, text in self.sources()
                 if re.search(r"\bLoadLibraryExW\s*\(", re.sub(r"/\*.*?\*/", "", text, flags=re.S))]
        self.assertEqual(loads, ["native/shared/patcher_files.h"])

    @unittest.skipUnless(CL.exists(), "MSVC is not installed")
    def test_the_path_builder_harness(self):
        script = ROOT / "scripts" / "build_patcher_files_harness.ps1"
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-3000:])
        self.assertIn("all patcher_files checks passed", result.stdout)


def publish(test: unittest.TestCase, game: str, selection, *, prepare=None, overwrite=False,
            temp: Path | None = None):
    build = build_of(game)
    if temp is None:
        holder = tempfile.TemporaryDirectory()
        test.addCleanup(holder.cleanup)
        temp = Path(holder.name)
    source = temp / build.title
    if not source.exists():
        source.mkdir()
        shutil.copy2(stock_path(game), source / build.input_name)
        (source / "Images").mkdir()
        (source / "Images" / "stock_art.png").write_bytes(b"a stock image")
    if prepare is not None:
        prepare(source, temp)
    output, log_path = vfp.apply_patch(source / build.input_name, "collection_progression",
                                       fun_patch_ids=list(selection), overwrite=overwrite)
    return source, output, log_path, temp


def tree(folder: Path) -> dict[str, Path]:
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class ThePublishedLayout(unittest.TestCase):

    def test_every_game_with_every_public_patch(self):
        for game in GAMES:
            with self.subTest(game=game):
                source, output, log_path, _ = publish(self, game, public_ids(game))
                out = output.parent
                before, after = tree(source), tree(out)
                added = sorted(set(after) - set(before))
                in_place = {k.casefold() for k in patcher_files.GAME_READS_IN_PLACE}
                outside = [a for a in added if not a.startswith(FOLDER + "/") and a != output.name]
                self.assertEqual([a for a in outside if a.casefold() not in in_place], [])
                # The two reports, in the folder; nothing of the patcher's loose.
                self.assertEqual(log_path, out / FOLDER / patcher_files.patch_log_name(output.name))
                self.assertTrue((out / patcher_files.TRANSPARENCY_RELATIVE_PATH).is_file())
                self.assertEqual([p for p in out.glob("*") if p.name.startswith("VVFP ")
                                  or p.name.endswith(".patch-log.json")], [])
                self.assertTrue((out / FOLDER / vfp.STARTUP_LOADER_DLL).is_file())
                log = json.loads(log_path.read_text(encoding="utf-8"))
                for record in log["companion_files"]:
                    relative = Path(record["path"]).relative_to(out).as_posix()
                    self.assertEqual(relative, vfp._safe_companion_destination(
                        relative.removeprefix(FOLDER + "/")).as_posix())
                self.assertEqual(log["transparency_log_path"], f"{FOLDER}/VVFP Transparency Log.txt")
                # Every DLL the build ships is in the folder.
                for name in after:
                    if name.lower().endswith(".dll"):
                        self.assertTrue(name.startswith(FOLDER + "/"), name)


def make_old_layout(out: Path) -> dict[str, bytes]:
    """Turn a published folder into what v1.35.58 left: every file of the
    patcher's folder loose beside the executable, the logs too."""
    moved = {}
    files = out / FOLDER
    for path in sorted(files.rglob("*"), reverse=True):
        if path.is_file():
            target = out / path.relative_to(files)
            target.parent.mkdir(parents=True, exist_ok=True)
            path.replace(target)
            moved[target.relative_to(out).as_posix()] = target.read_bytes()
    shutil.rmtree(files)
    return moved


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class RepatchingAnOlderFolder(unittest.TestCase):

    def run_case(self, game, first, second, cleanup=True):
        source, output, _, temp = publish(self, game, first)
        out = output.parent
        loose = make_old_layout(out)
        (out / "my notes.txt").write_text("the player's own", encoding="utf-8")
        (out / "Images" / "my_art.png").write_bytes(b"the player's art")
        (out / "VVFP Notes.txt").write_text("a player file named like ours", encoding="utf-8")
        if not cleanup:
            original = vfp._patcher_owned_companion_keys
            self.addCleanup(setattr, vfp, "_patcher_owned_companion_keys", original)
            vfp._patcher_owned_companion_keys = lambda build, folder: set()
        _, output2, log2, _ = publish(self, game, second, overwrite=True, temp=temp)
        return loose, out, tree(out), log2

    def test_the_loose_files_go_and_the_players_stay(self):
        for game, first, second in (
            ("vv1", public_ids("vv1"), ["vv1_write_village_statistics"]),
            ("vv4", public_ids("vv4"), public_ids("vv4")),
        ):
            with self.subTest(game=game):
                loose, out, after, log = self.run_case(game, first, second)
                self.assertTrue(loose)
                in_place = {k.casefold() for k in patcher_files.GAME_READS_IN_PLACE}
                for relative in loose:
                    if relative.casefold() in in_place:
                        continue
                    self.assertNotIn(relative, after, "an older patcher's loose file was kept")
                self.assertEqual(after["my notes.txt"].read_text(encoding="utf-8"), "the player's own")
                self.assertEqual(after["Images/my_art.png"].read_bytes(), b"the player's art")
                self.assertIn("VVFP Notes.txt", after)
                self.assertIn(f"{FOLDER}/{vfp.STARTUP_LOADER_DLL}", after)
                # Nothing twice: no DLL both loose and in the folder.
                names = [Path(r).name for r in after if r.lower().endswith(".dll")]
                self.assertEqual(len(names), len(set(names)))

    def test_the_mutation_without_ownership_keeps_them(self):
        loose, out, after, _ = self.run_case("vv1", public_ids("vv1"), ["vv1_write_village_statistics"],
                                             cleanup=False)
        self.assertIn("VVFP Fix Huts.dll", after)
        self.assertIn("VVFP Transparency Log.txt", after)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class ASourceFolderWithLooseCopies(unittest.TestCase):

    def test_they_are_removed_from_the_copy_only(self):
        game = "vv3"

        def seed(source: Path, _temp: Path) -> None:
            for _, item in catalog_items(game):
                if not str(item["destination"]).lower().endswith(".dll"):
                    continue
                src = ROOT / item["source"]
                if src.is_file():
                    shutil.copy2(src, source / item["destination"])
            shutil.copy2(ROOT / vfp.STARTUP_LOADER_COMPANION["source"], source / vfp.STARTUP_LOADER_DLL)

        source, output, log_path, _ = publish(self, game, ["vv3_builders_fix_huts"], prepare=seed)
        out = output.parent
        self.assertEqual([p.name for p in out.glob("VVFP *.dll")], [])
        self.assertTrue((out / FOLDER / "VVFP Fix Huts.dll").is_file())
        self.assertTrue(list(source.glob("VVFP *.dll")))          # the source is untouched
        log = json.loads(log_path.read_text(encoding="utf-8"))
        reasons = {r["path"]: r["reason"] for r in log["removed_unselected_companions"]}
        self.assertIn("VVFP Fix Huts.dll", reasons)
        self.assertIn("older patcher", reasons["VVFP Fix Huts.dll"])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class ATooDeepOutputFolder(unittest.TestCase):

    def test_the_boundary(self):
        """The longest path the build writes is measured in the hidden
        staging folder (42 characters longer than the output) -- here the
        patch log in the patcher's folder, which is longer than any DLL."""
        features = vfp._attach_automatic_companions(
            "vv1", vfp._selected_fun_patches(build_of("vv1"), ["vv1_builders_fix_huts"]))
        name = "Virtual Villagers - A New Home - Modded.exe"
        log = str(Path(*patcher_files.patch_log_relative_path(name).parts))
        longest_dll = max((str(vfp._safe_companion_destination(i["destination"]))
                           for f in features for i in f.raw.get("companion_files", [])), key=len)
        self.assertGreater(len(log), len(longest_dll))
        base = Path(os.path.abspath(tempfile.gettempdir()))
        # <base>\<folder>  and  <base>\.<folder>.staging-<32>\<log>
        room = patcher_files.MAX_PATH - 1 - len(str(base)) - 1 - len(".staging-") - 1 - 32 - 1 - len(log)
        ok = base / ("o" * room)
        staged = ok.parent / f".{ok.name}.staging-{'0' * 32}" / log
        self.assertEqual(len(str(staged)), patcher_files.MAX_PATH - 1)
        vfp._require_patcher_files_path_fits(ok, features, name)                       # 259: fits
        with self.assertRaises(vfp.PatcherError):
            vfp._require_patcher_files_path_fits(base / ("o" * (room + 1)), features, name)   # 260
        # The old check (only <output>\<longest DLL>) passed this folder.
        self.assertLess(len(str(base / ("o" * (room + 1)) / longest_dll)), patcher_files.MAX_PATH)

    def test_the_games_own_files_count_too(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        source = Path(holder.name) / "s"
        (source / "Sounds" / ("x" * 60)).mkdir(parents=True)
        (source / "Sounds" / ("x" * 60) / ("y" * 60 + ".ogg")).write_bytes(b"")
        out = Path(os.path.abspath(tempfile.gettempdir())) / ("o" * 80)
        vfp._require_patcher_files_path_fits(out, [], "g.exe")                      # without them: fits
        with self.assertRaises(vfp.PatcherError):
            vfp._require_patcher_files_path_fits(out, [], "g.exe", source)

    def test_nothing_is_written(self):
        game = "vv1"
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        temp = Path(holder.name)
        source = temp / "s"
        source.mkdir()
        shutil.copy2(stock_path(game), source / build_of(game).input_name)
        deep = temp / ("d" * (patcher_files.MAX_PATH - len(str(temp)) - 20))
        with self.assertRaises(vfp.PatcherError) as raised:
            vfp.apply_patch(source / build_of(game).input_name, "collection_progression",
                            fun_patch_ids=["vv1_builders_fix_huts"], output_root=deep)
        self.assertIn("too long", str(raised.exception))
        self.assertFalse(deep.exists())

    def test_windows_utf16_units_are_counted(self):
        """An emoji is two WCHARs to Windows; a path Python measures as 259
        characters is then 260 units and must be refused."""
        base = Path(os.path.abspath(tempfile.gettempdir()))
        staging_extra = len(".staging-") + 32 + 1   # ".<name>.staging-<32>" vs "<name>"
        log = str(Path(*patcher_files.TRANSPARENCY_RELATIVE_PATH.parts))
        room = patcher_files.MAX_PATH - 1 - len(str(base)) - 1 - staging_extra - 1 - len(log)
        fits = base / ("o" * room)
        vfp._require_patcher_files_path_fits(fits, [], "")
        emoji = base / ("o" * (room - 1) + "\U0001F600")   # same len(), one more unit
        self.assertEqual(len(str(emoji)), len(str(fits)))
        with self.assertRaises(vfp.PatcherError):
            vfp._require_patcher_files_path_fits(emoji, [], "")

    def test_reports_from_an_earlier_build_in_the_source_are_dropped(self):
        """A source folder an older patcher produced carries that build's loose
        reports (and a patch log under another executable name); the staged
        copy drops the signed ones and keeps a player's look-alike."""
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        staging = Path(holder.name)
        signed = json.dumps({"patcher": "Virtual Villagers Fun Patcher"})
        inner = staging / patcher_files.PATCHER_FILES_FOLDER
        inner.mkdir()
        (staging / patcher_files.TRANSPARENCY_FILENAME).write_text("old", encoding="utf-8")
        (staging / ("Old - Modded" + patcher_files.PATCH_LOG_SUFFIX)).write_text(signed, encoding="utf-8")
        (inner / ("Other" + patcher_files.PATCH_LOG_SUFFIX)).write_text(signed, encoding="utf-8")
        mine = staging / ("Mine" + patcher_files.PATCH_LOG_SUFFIX)
        mine.write_text('{"patcher": "someone else"}', encoding="utf-8")
        removed = vfp._remove_unselected_companions(staging, build_of("vv1"), [])
        self.assertEqual(
            sorted(item["path"] for item in removed),
            sorted([
                patcher_files.TRANSPARENCY_FILENAME,
                "Old - Modded" + patcher_files.PATCH_LOG_SUFFIX,
                f"{patcher_files.PATCHER_FILES_FOLDER}/Other{patcher_files.PATCH_LOG_SUFFIX}",
            ]),
        )
        self.assertTrue(mine.is_file())

    @unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
    def test_apply_all_checks_every_game_before_publishing_any(self):
        """A later game too long for MAX_PATH must stop the bulk build before
        the first game is published, not after."""
        from unittest import mock

        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        sources = {}
        for game in GAMES:
            folder = Path(holder.name) / game
            folder.mkdir()
            shutil.copy2(stock_path(game), folder / build_of(game).input_name)
            sources[game] = folder
        calls = []

        def refuse_the_last(*args, **kwargs):
            calls.append(args)
            if len(calls) == len(GAMES):
                raise vfp.PatcherError("too long")

        with mock.patch.object(vfp, "_require_patcher_files_path_fits", refuse_the_last), \
                mock.patch.object(vfp, "apply_patch") as publish:
            with self.assertRaises(vfp.PatcherError):
                vfp.apply_all(sources, output_root=Path(holder.name) / "out")
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
