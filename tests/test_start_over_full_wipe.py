"""Start Over wipes the whole save (the owner, v1.35.79), in all five games.

"Start Over" is the one exception to "nothing is ever deleted": it makes a new tribe, so every
remnant of the old one goes.  The on-disk behaviour is proven by native/shared/save_reset_harness.c
(built and run by tests/test_start_over_reset_without_origins.py when the 32-bit toolchain is
installed); these tests pin the rules in the source, the shipped companion, and the owner's
disclaimer in every place a player reads about Start Over.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RESET_C = ROOT / "native" / "shared" / "save_reset.c"
HARNESS = ROOT / "native" / "shared" / "save_reset_harness.c"
DLL = ROOT / "assets" / "save_reset" / "VVFP Save Reset.dll"

# The owner's words, exactly.
DISCLAIMER = (
    "Start Over wipes everything the Fun Patcher kept for that save: all its logs (the Village History "
    "too), all its data (ElderTotems.dat too) and its family tree files. It keeps Backups, Copies Made "
    "Before Repairs and exported family tree pictures. Other saves are not touched."
)


def flat(text: str) -> str:
    """Text with its line breaks and runs of spaces made single spaces."""
    return re.sub(r"\s+", " ", text)


def wipe_source() -> str:
    text = RESET_C.read_text(encoding="utf-8")
    return text[text.index("START OVER WIPES THE WHOLE SAVE"):text.index("int vv_reset_slot_state(")]


class TheWipeRulesTests(unittest.TestCase):
    def test_the_reset_ends_with_the_wipe(self) -> None:
        text = RESET_C.read_text(encoding="utf-8")
        body = text[text.index("int vv_reset_slot_state("):]
        self.assertIn("removed += wipe_slot(game, slot, village);\n    return removed;\n}", body)

    def test_what_is_wiped(self) -> None:
        wipe = wipe_source()
        for folder in ('L"Virtual Villagers Fun Patcher"', 'L"Virtual Villagers Fun Patcher Logs"',
                       'L"Virtual Villagers Fun Patcher Data"', 'L"Virtual Villagers Fun Patcher Family Trees"',
                       'L"Genealogy"'):
            with self.subTest(folder=folder):
                self.assertIn(folder, wipe)
        self.assertIn("wipe_walk(&w, top, WIPE_DATA, 0);", wipe)
        self.assertIn("wipe_walk(&w, top, WIPE_TREES, 0);", wipe)

    def test_what_is_always_kept(self) -> None:
        wipe = wipe_source()
        for picture in ('L".png"', 'L".jpg"', 'L".jpeg"', 'L".bmp"', 'L".gif"'):
            with self.subTest(picture=picture):
                self.assertIn(picture, wipe[wipe.index("static int wipe_is_picture("):])
        kept = wipe[wipe.index("static int wipe_is_kept_folder("):]
        self.assertIn('L"Backups"', kept[:400])
        self.assertIn('L"Copies Made Before Repairs"', kept[:400])
        self.assertIn('L".before-"', wipe)

    def test_links_are_never_followed_and_nothing_is_retried(self) -> None:
        wipe = wipe_source()
        walk = wipe[wipe.index("static void wipe_walk("):wipe.index("static int wipe_folder(")]
        self.assertIn("FILE_ATTRIBUTE_REPARSE_POINT", walk)
        self.assertLess(walk.index("FILE_ATTRIBUTE_REPARSE_POINT"), walk.index("wipe_walk(w, path, mode, depth + 1)"))
        self.assertIn("WIPE_DEPTH_MAX", walk)
        # A file that cannot be deleted is noted once: no loop around the delete.
        delete = wipe[wipe.index("static void wipe_delete("):wipe.index("static void wipe_file(")]
        self.assertNotIn("while", delete)
        self.assertNotIn("for (", delete)
        self.assertNotIn("Sleep", wipe)

    def test_a_tree_file_is_told_by_the_save_it_records(self) -> None:
        wipe = wipe_source()
        self.assertIn('L".vvtree"', wipe)
        self.assertIn('memcmp(text + key_start, "slot", 4)', wipe)
        self.assertIn("have_key = depth == 1;", wipe, "only the top level's \"slot\" counts")
        # src/vv_genealogy_window.py writes that key, and names the file "(Save N)".
        window = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertIn('"slot": self.slot', window)
        self.assertIn('f"{tribe} (Save {self.slot}) Family Tree{TREE_SUFFIX}"', window)
        tree = (ROOT / "src" / "vv_family_tree.py").read_text(encoding="utf-8")
        self.assertIn('f"Virtual Villagers {game} Village Matchmaker - Save {slot}.txt"', tree)
        self.assertIn('f"Virtual Villagers {game} Genealogy - Save {slot}"', tree)

    def test_the_report_names_what_was_kept(self) -> None:
        wipe = wipe_source()
        self.assertIn('L"Start Over Report - Save "', wipe)
        self.assertIn("Kept, its save could not be told", wipe)
        self.assertIn("Could not be deleted", wipe)
        self.assertIn("Not followed (a link or junction)", wipe)

    def test_the_harness_covers_all_five_games(self) -> None:
        harness = HARNESS.read_text(encoding="utf-8")
        cases = harness[harness.index("static void full_wipe_cases("):harness.index("int main(void)")]
        self.assertIn("for (game = 1; game <= 5; ++game) {", cases)
        for wanted in ("START OVER DELETES EVERYTHING IN", "A FILE PATH KEPT FROM BEFORE START OVER CAN STILL BE WRITTEN",
                       "SAVE 2'S OWN FOLDER IS UNTOUCHED", "SLOT 1'S .vvtree IS DELETED",
                       "is KEPT (never guessed)", "SLOT 1'S VILLAGE MATCHMAKER IS DELETED", "EVERY PICTURE IS KEPT",
                       "THE BACKUPS ARE KEPT", "COPIES MADE BEFORE REPAIRS ARE KEPT",
                       "A JUNCTION OUT OF THE SAVE FOLDER IS NEVER FOLLOWED",
                       "A FILE IN USE IS LEFT, COUNTED ONCE"):
            with self.subTest(case=wanted):
                self.assertIn(wanted, cases)
        # The harness never touches the player's saves: it refuses unless the folder it resolved is
        # inside the throwaway Documents under %TEMP%.
        self.assertIn("the save folder is not under the throwaway Documents", harness)

    def test_the_shipped_companion_carries_the_wipe(self) -> None:
        blob = DLL.read_bytes()
        self.assertIn("Start Over Report - Save ".encode("utf-16-le"), blob)
        self.assertIn("Virtual Villagers Fun Patcher Family Trees".encode("utf-16-le"), blob)
        self.assertIn(b"Kept, its save could not be told", blob)


class TheDisclaimerTests(unittest.TestCase):
    def test_the_statistics_patches_say_it_in_all_five_games(self) -> None:
        manifest = json.loads((ROOT / "data" / "statistics_features.json").read_text(encoding="utf-8"))
        games = {feature["game_id"]: feature["description"] for feature in manifest["features"]}
        self.assertEqual({"vv1", "vv2", "vv3", "vv4", "vv5"}, set(games))
        for game, description in games.items():
            with self.subTest(game=game):
                self.assertIn(DISCLAIMER, description)
        builder = (ROOT / "scripts" / "build_statistics_features.py").read_text(encoding="utf-8")
        self.assertIn(DISCLAIMER, "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', builder)))

    def test_the_readme_says_it(self) -> None:
        self.assertIn(DISCLAIMER, (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_how_to_use_says_it(self) -> None:
        self.assertIn(DISCLAIMER, flat((ROOT / "How to Use.txt").read_text(encoding="utf-8")))
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        guide = " ".join(guides["controls"]["back_up_saves"]["guide"])
        # The "?" guides allow no file extensions, so the Elder Totems are named in words.
        for part in ("Start Over wipes everything the Fun Patcher kept for that save", "(the Village History too)",
                     "family tree files", "Backups, Copies Made Before Repairs", "Other saves are not touched."):
            with self.subTest(part=part):
                self.assertIn(part, guide)

    def test_the_patcher_window_says_it_by_the_save_folders(self) -> None:
        import vv_fun_patcher_gui as gui
        self.assertEqual(DISCLAIMER, gui.START_OVER_DISCLAIMER)
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        line = source.index("Save N's logs and data: {save_root}")
        self.assertIn("artifact_lines.append(START_OVER_DISCLAIMER)", source[line:line + 1200])

    def test_no_game_text_is_changed(self) -> None:
        """The games' own Start Over question keeps its words in all five games.  Four keep it in
        the executable, where no text is changed; The Tree of Life's optional text swap could carry
        it, but its patch refuses any Assets/sm.xml that is neither the stock file nor its own exact
        file, so changing that file would refuse every game already patched with the current one
        (and how much text the question box shows is not known): the disclaimer is in the patcher."""
        base = (ROOT / "assets" / "text-changes" / "vv4-sm-base.xml").read_text(encoding="utf-8")
        edited = (ROOT / "assets" / "text-changes" / "vv4-sm.xml").read_text(encoding="utf-8")
        question = re.compile(r'<Text id="eSayConfirmRestart">\s*(.*?)\s*</Text>', re.S)
        self.assertEqual(question.search(base).group(1), question.search(edited).group(1))
        self.assertEqual("Are you sure you want to restart the current game?", question.search(edited).group(1))


if __name__ == "__main__":
    unittest.main()
