"""The installed patches' list (v1.35.97): Custom Island Events' patch conditions know every installed patch.

* The patcher writes "Virtual Villagers Fun Patcher Files\\VVFP Installed Patches.txt" at every patch: the game
  build's id and every fun patch installed, one per line, sorted, "#" lines notes (vv_fun_patcher.
  installed_patches_text); a re-patch rewrites it (fewer patches: fewer lines), and an earlier build's list in the
  source folder is dropped from the copy like its other reports.
* The Story / Cheat Upgrades companion (story_graph.inc cg_installed_has, emulated with the TEST build) reads an
  event's patch id as the short name: the line itself or the line without its "vv<N>_" prefix in game N (a build
  id's "_rewrite" ending too); another game's patch never counts; without a list (an older patch) only Guardians of
  Isola's own detection is left.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import patcher_files  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
import vv_fun_patcher as vfp  # noqa: E402
from test_patcher_files_folder import STOCK_ABSENT, STOCK_PRESENT, build_of, publish, short_base  # noqa: E402

from test_story_cie_graph_runtime import GRAPH, HAVE_EMULATOR, Run, emulated, have_stock  # noqa: E402

HAVE_RUN = HAVE_EMULATOR


def listed(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


class TheText(unittest.TestCase):
    def test_the_build_and_every_patch_sorted_with_notes_first(self) -> None:
        build = build_of("vv3")
        patches = [vfp.get_fun_patch("vv3_more_island_events"), vfp.get_fun_patch("vv3_scrolling_popups")]
        text = vfp.installed_patches_text(build, patches)
        self.assertTrue(text.startswith("# "))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(listed(text), sorted(["vv3", "vv3_more_island_events", "vv3_scrolling_popups"]))
        self.assertEqual(listed(vfp.installed_patches_text(build, patches, ["vv3_scrolling_popups"])),
                         ["vv3", "vv3_more_island_events"])
        text.encode("ascii")

    def test_its_place_and_name(self) -> None:
        self.assertEqual(patcher_files.INSTALLED_PATCHES_RELATIVE_PATH.as_posix(),
                         f"{patcher_files.PATCHER_FILES_FOLDER}/VVFP Installed Patches.txt")
        story = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        self.assertIn('#define CG_INSTALLED_LEAF "VVFP Installed Patches.txt"', story)

    def test_an_earlier_builds_list_is_dropped_from_the_copy(self) -> None:
        staging = short_base(self)
        inner = staging / patcher_files.PATCHER_FILES_FOLDER
        inner.mkdir()
        (inner / patcher_files.INSTALLED_PATCHES_FILENAME).write_text("vv1\nvv1_old\n", encoding="ascii")
        removed = vfp._remove_unselected_companions(staging, build_of("vv1"), [])
        self.assertIn(patcher_files.INSTALLED_PATCHES_RELATIVE_PATH.as_posix(), [item["path"] for item in removed])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class EveryPatch(unittest.TestCase):
    def test_written_at_a_patch_and_rewritten_at_a_repatch(self) -> None:
        for game in ("vv1", "vv3", "vv5"):
            with self.subTest(game=game):
                # More Island Events needs Story / Cheat Upgrades (its rare roll and Pick Island Event).
                ids = [f"{game}_more_island_events", f"{game}_scrolling_popups", f"{game}_story_cheat_upgrades"]
                source, output, _log, temp = publish(self, game, ids)
                path = output.parent / patcher_files.INSTALLED_PATCHES_RELATIVE_PATH
                first = listed(path.read_text(encoding="ascii"))
                self.assertIn(game, first)
                for patch_id in ids:
                    self.assertIn(patch_id, first)
                self.assertEqual(first, sorted(first))
                transparency = (output.parent / patcher_files.TRANSPARENCY_RELATIVE_PATH).read_text(encoding="utf-8")
                self.assertIn("Installed patches list: Virtual Villagers Fun Patcher Files/VVFP Installed Patches.txt",
                              transparency)
                _s, output2, _l, _t = publish(self, game, [ids[0], ids[2]], overwrite=True, temp=temp)
                again = listed((output2.parent / patcher_files.INSTALLED_PATCHES_RELATIVE_PATH).read_text("ascii"))
                self.assertIn(ids[0], again)
                self.assertNotIn(ids[1], again)


@unittest.skipUnless(HAVE_RUN and have_stock("vv3") and have_stock("vv5"), "needs the stock executables")
@emulated
class TheCompanionReadsIt(unittest.TestCase):
    def on(self, run: Run, game: int, text: str | None) -> int:
        if text is None:
            return run.p.export("VvfpStoryProbeInstalledPatches", game, 0)
        buf = run.p.alloc(len(text) + 1)
        run.p.write(buf, text.encode("ascii") + b"\0")
        return run.p.export("VvfpStoryProbeInstalledPatches", game, buf)

    def test_short_names_in_their_own_game(self) -> None:
        graph = dict(GRAPH)
        graph["patches"] = ["guardians_of_isola", "scrolling_popups", "more_island_events"]
        data = cg.compile_graph(cg.load(graph))
        for game in ("vv3", "vv5"):
            with self.subTest(game=game):
                n = int(game[-1])
                run = Run(game)
                run.queue(data)                    # loads it as the companion's graph (a refusal is fine here)
                text = f"# notes\r\n{game}\r\n{game}_scrolling_popups\r\nvv1_more_island_events\r\n"
                self.assertEqual(self.on(run, n, text) & 0b110, 0b010)       # another game's never counts
                self.assertEqual(self.on(run, n, text + "more_island_events\n") & 0b110, 0b110)  # a bare id
                self.assertEqual(self.on(run, n, "") & 0b110, 0)
                self.assertEqual(self.on(run, n, None) & 0b110, 0)                # no list: only Guardians'
                if game == "vv5":
                    self.assertEqual(self.on(run, n, "vv5\nvv5_guardians_of_isola_rewrite\n") & 1, 1)


if __name__ == "__main__":
    unittest.main()
