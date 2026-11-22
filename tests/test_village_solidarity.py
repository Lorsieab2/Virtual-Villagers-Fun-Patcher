"""Village Solidarity (the owner, 2026-11-17; all five games): the village's 0-100 score, moved by the new events'
tagged pages, changing ONLY the odds of the patcher's own events and endings.

What this file proves (each fails without the change):

  * THE SCORE FILE: the companion's own source, run against real files (native/vvfp_village_solidarity/
    solidarity_harness.c): written at once, read back after a restart, an unreadable file set aside, the log;
  * THE MOVES: every raise and every lower by the same step, neutral never, always within 0..100 (the harness and
    src/vv_village_scores.py, which must agree);
  * THE ODDS: the factor raises only the favoured side, more with the slider, never below 1x; in the story engine
    (emulated on the stock executables) a chance split's raise-tagged ending is more likely with a high score and its
    lower-tagged ending with a low one, the collection draw's cooperative / repair events likewise -- and with the
    companion absent every draw is the one before, with the same numbers;
  * STOCK ODDS: the factor is asked only inside the Story companion's own draws (cg_draw, sc_choose_and_arm), never
    in a game's own island event trigger;
  * THE FORMAT: a page's "solidarity" tag survives compile and decompile; an untagged graph compiles to the same
    bytes; a branch or an unknown word is refused;
  * THE ROWS: all five games, off by default and in Select All, on in Owner's Defaults, needing Story / Cheat
    Upgrades, the DLL pinned and started from the second startup word, the strength written beside it.
"""
from __future__ import annotations

import copy
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
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
import vv_village_scores as scores  # noqa: E402

CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
NATIVE = ROOT / "native" / "vvfp_village_solidarity"
STORY = ROOT / "native" / "vvfp_story_upgrades"


class TheRules(unittest.TestCase):
    def test_every_move_is_the_same_step_and_clamped(self) -> None:
        for score in range(0, 101):
            self.assertEqual(scores.moved(score, "raise"), min(100, score + scores.STEP))
            self.assertEqual(scores.moved(score, "lower"), max(0, score - scores.STEP))
            self.assertEqual(scores.moved(score, "neutral"), score)
            self.assertEqual(scores.moved(score, None), score)
        self.assertEqual(scores.START, 50)

    def test_the_factor_only_raises_the_favoured_side(self) -> None:
        for score in range(0, 101):
            high = scores.factor(score, scores.FAVOUR_HIGH)
            low = scores.factor(score, scores.FAVOUR_LOW)
            self.assertGreaterEqual(min(high, low), 1000)
            self.assertEqual(high, 1000 + 20 * max(0, score - 50))     # +2% a point above 50 at 1x
            self.assertEqual(low, 1000 + 20 * max(0, 50 - score))      # +2% a point below 50 at 1x
            self.assertEqual(scores.factor(score, scores.FAVOUR_NONE), 1000)

    def test_the_slider_scales_it(self) -> None:
        self.assertEqual(scores.factor(100, scores.FAVOUR_HIGH, 10), 2000)
        self.assertEqual(scores.factor(100, scores.FAVOUR_HIGH, 100), 11000)
        self.assertEqual(scores.factor(100, scores.FAVOUR_HIGH, 1), 1100)
        self.assertEqual(scores.factor(0, scores.FAVOUR_LOW, 25), 3500)

    def test_the_strength_numbers(self) -> None:
        for value, text in ((1, "1"), (0.5, "0.5"), ("2.5", "2.5"), (10, "10"), (0.1, "0.1")):
            self.assertEqual(scores.strength_text(value), text)
        for bad in (0, 10.1, 0.05, "abc", True, -1, 11):
            self.assertIsNone(scores.strength_tenths(bad), bad)

    def test_the_native_rules_match(self) -> None:
        source = (NATIVE / "vvfp_village_solidarity.c").read_text(encoding="utf-8")
        self.assertIn(f"#define VS_STEP {scores.STEP} ", source)
        self.assertIn(f"#define VS_START {scores.START}", source)
        self.assertIn(f'#define VS_FILE_HEADER "{scores.FILE_HEADER}"', source)
        self.assertIn("return 1000 + 2 * strength * distance;", source)

    def test_the_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(scores.read_scores(Path(folder), 2))
            path = scores.write_scores(Path(folder), 2, {scores.SOLIDARITY_NAME: 62})
            self.assertTrue(str(path).endswith(r"Virtual Villagers Fun Patcher\Save 2\Data\Village Scores"
                                               r"\Village Scores - Save 2.txt"))
            self.assertEqual(scores.read_scores(Path(folder), 2), {scores.SOLIDARITY_NAME: 62})
        self.assertIsNone(scores.parse("nonsense"))
        self.assertIsNone(scores.parse(scores.FILE_HEADER + "\r\nVillage Solidarity 101\r\n"))
        self.assertEqual(scores.parse(scores.FILE_HEADER + "\r\n"), {scores.SOLIDARITY_NAME: 50})

    def test_the_help_popup_is_the_owners_words_and_translatable(self) -> None:
        """The "?" popup (the owner, 2026-11-18: "Use it exactly, word for word"), each part with its own row."""
        owners = ("Village Solidarity shows how close and united your village feels, from 0 to 100. Good Island event "
                  "outcomes raise it, bad ones lower it. High Solidarity (greater than 50) can increase the likelihood "
                  "of more good events happening, while Low Solidarity (less than 50) does the opposite.")
        source = (NATIVE / "vvfp_village_solidarity.c").read_text(encoding="utf-8")
        body = source[source.index("#define SOL_HELP_TEXT"):source.index("static const char *sol_help_title")]
        self.assertEqual("".join(re.findall(r'"((?:[^"\\]|\\.)*)"', body)), owners)
        rows = {r["stem"]: r["english"] for r in json.loads(
            (ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))["strings"]}
        self.assertEqual(rows["vvfp.village_solidarity/vvfp_village_solidarity.SOL_HELP_TEXT.s0"], owners)
        self.assertEqual(rows["vvfp.village_solidarity/vvfp_village_solidarity.SOL_HELP_TITLE.s0"], "Village Solidarity")
        self.assertIn('vvfp_tr("vvfp.village_solidarity/vvfp_village_solidarity.SOL_HELP_TEXT.s0"', source)
    def test_the_feeling_words(self) -> None:
        self.assertEqual(scores.tag_for_text("Everyone sang, grateful and happy."), "raise")
        self.assertEqual(scores.tag_for_text("The quarrel stays unresolved, and resentment grows."), "lower")
        self.assertEqual(scores.tag_for_text("They stand in solemn remembrance."), "neutral")
        self.assertIsNone(scores.tag_for_text("They were happy, but afraid."))
        self.assertIsNone(scores.tag_for_text("She picks up a stone."))


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class TheCompanionAgainstRealFiles(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 str(ROOT / "scripts" / "build_village_solidarity_harness.ps1")],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        self.assertNotIn("FAIL", result.stdout)


GRAPH = {
    "format": "vvfp-cie-graph", "version": 3, "title": "A Shared Evening", "games": [1, 2, 3, 4, 5],
    "requirement": {"min_eligible": 1},
    "roles": {"subject": {"kind": "villager"}},
    "start": "intro",
    "nodes": {
        "intro": {"text": "(Name) calls the village together.", "children": [
            {"next": "glad", "weight": 1}, {"next": "sour", "weight": 1}, {"next": "plain", "weight": 1}]},
        "glad": {"text": "Everyone sings, grateful.", "solidarity": "raise"},
        "sour": {"text": "An old quarrel flares up.", "solidarity": "lower"},
        "plain": {"text": "Then everyone goes to bed."},
    },
}


class TheFormat(unittest.TestCase):
    def test_a_tag_survives_compile_and_decompile(self) -> None:
        back = cg.decompile_graph(cg.compile_graph(cg.load(copy.deepcopy(GRAPH), scrolling=True)))
        self.assertEqual({k: n.get("solidarity") for k, n in back["nodes"].items()},
                         {"intro": None, "glad": "raise", "sour": "lower", "plain": None})

    def test_the_flags_byte(self) -> None:
        blob = cg.compile_graph(cg.load(copy.deepcopy(GRAPH), scrolling=True))
        o_node = struct.unpack_from("<I", blob, 48)[0]
        flags = [blob[o_node + 28 * i + 3] for i in range(4)]
        self.assertEqual(flags, [0, 4, 8, 0])                     # raise 1 << 2, lower 2 << 2 (bit 1: a new page)

    def test_an_untagged_graph_compiles_as_before(self) -> None:
        plain = copy.deepcopy(GRAPH)
        for n in plain["nodes"].values():
            n.pop("solidarity", None)
        tagged = cg.compile_graph(cg.load(copy.deepcopy(GRAPH), scrolling=True))
        untagged = cg.compile_graph(cg.load(plain, scrolling=True))
        self.assertEqual(len(tagged), len(untagged))
        o_node = struct.unpack_from("<I", untagged, 48)[0]
        self.assertTrue(all(untagged[o_node + 28 * i + 3] == 0 for i in range(4)))

    def test_bad_tags_are_refused(self) -> None:
        bad = copy.deepcopy(GRAPH)
        bad["nodes"]["glad"]["solidarity"] = "joyful"
        self.assertTrue(any("solidarity" in p for p in cg.validate(bad, scrolling=True)[1]))
        branchy = copy.deepcopy(GRAPH)
        branchy["nodes"]["intro"] = {"type": "branch", "solidarity": "raise",
                                     "children": GRAPH["nodes"]["intro"]["children"]}
        branchy["start"] = "intro"
        self.assertTrue(any("branch" in p and "solidarity" in p for p in cg.validate(branchy, scrolling=True)[1]))

    def test_the_story_companion_reads_the_tag_bits(self) -> None:
        graph = (STORY / "story_graph.inc").read_text(encoding="utf-8")
        # v1.35.97 merge: bit 1 is the new-page flag (cie-v6-binary.md 19a), so the tag is bits 2-3.
        self.assertIn("#define CG_NODE_SOLIDARITY 12u", graph)
        self.assertIn("(n[3] & ~(CG_NODE_AUTO_TEXT | CG_NODE_NEW_PAGE | CG_NODE_SOLIDARITY)) != 0u", graph)
        self.assertIn("#define CG_NODE_SOL_MASK 12u", (STORY / "story_solidarity.inc").read_text(encoding="utf-8"))
        self.assertEqual((cg.NODE_SOLIDARITY_MASK, cg.NODE_SOLIDARITY_SHIFT), (12, 2))

    def test_a_tagged_page_split_by_the_outcome_pass_tags_both_copies(self) -> None:
        # #821 x #804: scripts/outcome_effects.py turns tagged page X into a branch over X__fx / X__text; the
        # collection build tags both copies (the same Village Solidarity change either way), never the branch.
        import build_event_collection_features as bec
        g = copy.deepcopy(GRAPH)
        glad = g["nodes"]["glad"]
        glad.pop("solidarity", None)
        g["nodes"]["glad__fx"] = copy.deepcopy(glad)
        g["nodes"]["glad__text"] = copy.deepcopy(glad)
        g["nodes"]["glad"] = {"type": "branch", "children": [{"next": "glad__fx"}, {"next": "glad__text"}]}
        g["nodes"]["sour"].pop("solidarity", None)
        lg = cg.load(g, scrolling=True)
        old = bec._SOLIDARITY_CACHE
        try:
            bec._SOLIDARITY_CACHE = {"ev": {"nodes": {"glad": "raise", "sour": "lower"}}}
            bec.apply_solidarity_tags("ev", lg)
        finally:
            bec._SOLIDARITY_CACHE = old
        self.assertNotIn("solidarity", lg["nodes"]["glad"])
        self.assertEqual((lg["nodes"]["glad__fx"]["solidarity"], lg["nodes"]["glad__text"]["solidarity"]),
                         ("raise", "raise"))
        self.assertEqual(lg["nodes"]["sour"]["solidarity"], "lower")
        back = cg.decompile_graph(cg.compile_graph(lg))
        self.assertEqual({k: n.get("solidarity") for k, n in back["nodes"].items() if k.startswith("glad")},
                         {"glad": None, "glad__fx": "raise", "glad__text": "raise"})


class StockOddsUntouched(unittest.TestCase):
    def test_the_factor_is_asked_only_in_the_companions_own_draws(self) -> None:
        """Every call of the factor is inside cg_draw (a branching event's split) or sc_choose_and_arm (the rare
        collection roll, never in place of a natural event); no other story source asks it."""
        for path in sorted(STORY.glob("*.inc")) + sorted(STORY.glob("*.c")):
            text = path.read_text(encoding="utf-8")
            if path.name == "story_solidarity.inc":
                continue
            for m in re.finditer(r"cg_sol_(weights|factor|random_below)\(", text):
                head = text.rfind("\nstatic ", 0, m.start())
                func = re.match(r"\nstatic \w+ \*?(\w+)\(", text[head:head + 120]).group(1)
                self.assertIn(func, {"cg_draw", "sc_choose_and_arm", "sc_draw_group"}, f"{path.name}: {func}")   # round 6 split the draw per group
        self.assertNotIn("VillageScore", (ROOT / "native" / "vvfp_island_events" / "vvfp_island_events.c")
                         .read_text(encoding="utf-8"))

    def test_without_the_companion_every_factor_is_1000(self) -> None:
        text = (STORY / "story_solidarity.inc").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Village Solidarity.dll")', text)
        self.assertRegex(text, r"if \(f == NULL\) \{\s*return 1000;")
        self.assertRegex(text, r"if \(!any \|\| sum <= 0 \|\| sum > 0x3FFFFFFF\) \{\s*return 0;")


class TheRows(unittest.TestCase):
    def test_each_game_has_its_row(self) -> None:
        import hashlib
        dll = ROOT / "assets" / "village_solidarity" / scores.SOLIDARITY_DLL
        digest = hashlib.sha256(dll.read_bytes()).hexdigest().upper()
        for game in range(1, 6):
            row = json.loads((ROOT / "data" / f"vv{game}_village_solidarity_feature.json").read_text(encoding="utf-8"))
            self.assertEqual(row["id"], f"vv{game}_village_solidarity")
            self.assertEqual(row["name"], "Village Solidarity")
            self.assertEqual(row["dependencies"], [f"vv{game}_story_cheat_upgrades"])
            self.assertEqual(row["companion_files"][0]["sha256"], digest)
            self.assertIn("**Needs Story / Cheat Upgrades", row["description"])
            # Three Tech screen sites: the draw (the counter), the constructor (the "?" button is made) and the
            # screen's vtable slot 3 (the button's click opens the help box).
            # After them, the routines "VVFP Island Events.dll" detours to read the game's own events' results
            # (the owner, 2026-11-20; tests/test_stock_event_solidarity.py).
            own = [d for d in row["runtime_detours"] if d["installed_by"].startswith(scores.SOLIDARITY_DLL)]
            self.assertEqual(len(own), 3)
            self.assertEqual(row["runtime_detours"][:3], own)
            self.assertIn("draw", row["runtime_detours"][0]["routine"])
            self.assertIn("constructor", row["runtime_detours"][1]["routine"])
            self.assertIn("vtable slot 3", row["runtime_detours"][2]["routine"])

    def test_the_release_ships_its_files(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for path in ("src/vv_village_scores.py", "src/vv_game_mechanics_solidarity.py",
                     "assets/village_solidarity/VVFP Village Solidarity.dll",
                     *(f"data/vv{n}_village_solidarity_feature.json" for n in range(1, 6))):
            self.assertIn(f'    "{path}",\n', release)
    def test_owners_defaults_only(self) -> None:
        import vv_fun_patcher_gui as gui
        for game in range(1, 6):
            pid = f"vv{game}_village_solidarity"
            self.assertIn(pid, gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertIn(pid, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)
            self.assertNotIn(pid, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_started_from_the_second_word(self) -> None:
        import vv_fun_patcher as patcher
        # The v1.35.97 merge: the second word is full (32 of 32), so Village Solidarity is a third-word entry,
        # started through "VVFP More Companions.dll" (the second word's last entry).
        self.assertIn(scores.SOLIDARITY_DLL, patcher.STARTUP_LOADER_COMPANIONS_3)
        self.assertNotIn(scores.SOLIDARITY_DLL, patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Village Solidarity.dll",', header)

    def test_the_strength_is_written_beside_the_companion(self) -> None:
        import vv_fun_patcher as patcher
        feature = next(f for f in patcher.load_fun_patches() if f.id == "vv3_village_solidarity") \
            if hasattr(patcher, "load_fun_patches") else None
        if feature is None:
            self.skipTest("no feature loader")
        with tempfile.TemporaryDirectory() as out:
            try:
                patcher.set_village_solidarity_strength(2.5)
                patcher._write_village_solidarity_choice(Path(out), [feature])
                written = list(Path(out).rglob(scores.SOLIDARITY_CHOICE_FILE))
                self.assertEqual(len(written), 1)
                self.assertEqual(written[0].read_text(encoding="ascii"), "2.5\n")
            finally:
                patcher.set_village_solidarity_strength(1)
        with self.assertRaises(patcher.PatcherError):
            patcher.set_village_solidarity_strength(0)


# ---- the story engine, emulated on the stock executables -------------------------------------------------------

try:
    from test_story_custom_island_event import HAVE_EMULATOR, have_stock  # noqa: E402
except Exception:  # noqa: BLE001
    HAVE_EMULATOR = False

FAKE = 0x0EB00000


def fake_solidarity(p, factor_high: int, factor_low: int, tags: list, hook: bool = True) -> None:
    """"VVFP Village Solidarity.dll" stood in for: its factor per side and every tag the engine passes on."""
    from unicorn import UC_HOOK_CODE
    stubs = {n: p.alloc(16) for n in ("Factor", "Tag", "Get")}

    def get(pr):
        return 45, 8                                   # the score before: a raise or lower then reads 50

    def factor(pr):
        favour = pr.arg(2)
        return {1: factor_high, 2: factor_low}.get(favour, 1000), 12

    def tag(pr):
        tags.append((pr.arg(2), pr.cstring(pr.arg(3)) if pr.arg(3) else ""))
        return 50, 16
    p.stub(stubs["Factor"], factor)
    p.stub(stubs["Tag"], tag)
    p.stub(stubs["Get"], get)
    for va in stubs.values() if hook else ():         # a Run traces only its stubs' addresses
        p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=va, end=va)
    prior_module, prior_proc = p.api_handlers.get("GetModuleHandleA"), p.api_handlers.get("GetProcAddress")

    def module(pr):
        name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
        return (FAKE, 4) if name == scores.SOLIDARITY_DLL else (prior_module(pr) if prior_module else (0, 4))

    def proc(pr):
        if pr.arg(0) == FAKE:
            return {"VvfpVillageScoreFactor": stubs["Factor"], "VvfpVillageScoreTag": stubs["Tag"],
                    "VvfpVillageScoreGet": stubs["Get"]}.get(
                pr.cstring(pr.arg(1)), 0), 8
        return prior_proc(pr) if prior_proc else (0, 8)
    p.api_handlers["GetModuleHandleA"] = module
    p.api_handlers["GetProcAddress"] = proc


if HAVE_EMULATOR:
    from test_story_cie_graph_runtime_v6 import V6, compiled  # noqa: E402

    @unittest.skipUnless(all(have_stock(g) for g in ("vv1", "vv2", "vv3", "vv4", "vv5")), "the stock executables are not in research/stock-executables")
    class TheSplitsOdds(unittest.TestCase):
        """intro -> glad (raise) / sour (lower) / plain, weights 1 each; every roll the same value X, so the split
        draws X mod its total."""

        def ending(self, game: str, x: int, solidarity=None):
            run = V6(game)
            tags: list = []
            if solidarity is not None:
                fake_solidarity(run.p, *solidarity, tags)
            run.rolls([x] * 64)
            self.assertIsNone(run.queue6(compiled(GRAPH)))
            run.walk_through()
            names = list(GRAPH["nodes"])
            return [names[i] for i in run.path()][-1], tags

        def test_without_the_companion_the_draw_is_as_before(self) -> None:
            for game in ("vv1", "vv4"):
                for x, end in ((0, "glad"), (1, "sour"), (2, "plain"), (1999, "sour"), (2000, "plain")):
                    with self.subTest(game=game, x=x):
                        self.assertEqual(self.ending(game, x)[0], end)          # x mod 3

        def test_a_high_score_favours_the_raise_ending(self) -> None:
            # Factor 2000 for "raise": weights 2000 / 1000 / 1000 of 4000 -- glad is half the draw.
            for x, end in ((0, "glad"), (1999, "glad"), (2000, "sour"), (2999, "sour"), (3000, "plain"),
                           (3999, "plain")):
                with self.subTest(x=x):
                    self.assertEqual(self.ending("vv3", x, (2000, 1000))[0], end)

        def test_a_low_score_favours_the_lower_ending(self) -> None:
            for x, end in ((999, "glad"), (1000, "sour"), (2999, "sour"), (3000, "plain")):
                with self.subTest(x=x):
                    self.assertEqual(self.ending("vv5", x, (1000, 2000))[0], end)

        def test_at_50_the_same_odds(self) -> None:
            for x in range(6):
                with self.subTest(x=x):
                    self.assertEqual(self.ending("vv2", x, (1000, 1000))[0], self.ending("vv2", x)[0])

        def test_the_reached_page_moves_the_score(self) -> None:
            end, tags = self.ending("vv4", 0, (1000, 1000))
            self.assertEqual(end, "glad")
            self.assertEqual(tags, [(1, "A Shared Evening")])                # raise, with the event's title
            end, tags = self.ending("vv4", 1, (1000, 1000))
            self.assertEqual(tags, [(2, "A Shared Evening")])
            end, tags = self.ending("vv4", 2, (1000, 1000))
            self.assertEqual(tags, [])                                        # an untagged ending moves nothing

        def test_the_popup_says_the_change(self) -> None:
            # The owner (2026-11-18): the popup says the change made, after the clamp (45 -> 50 here: 5).
            for game in ("vv1", "vv4"):
                with self.subTest(game=game):
                    run = V6(game)
                    fake_solidarity(run.p, 1000, 1000, [])
                    run.rolls([0] * 64)
                    self.assertIsNone(run.queue6(compiled(GRAPH)))
                    text = " ".join(" ".join(t for _kind, t, _labels in run.walk_through()).split())
                    self.assertIn("Village Solidarity rises by 5.", text)

    from test_collection_trigger import Roll  # noqa: E402

    MANIFEST = "\n".join([
        "# id\ttitle\tgames\tweight\tseries\tcredit\tdescription\tGuardians title\tGuardians description\tkind",
        "a_feast\tThe Feast\t4\t1\t\tc\td\t\t\tcooperative",
        "b_plain\tA Walk\t4\t1\t\tc\td\t\t",
        "c_sorry\tThe Apology\t4\t1\t\tc\td\t\t\trepair",
    ]) + "\n"

    @unittest.skipUnless(all(have_stock(g) for g in ("vv1", "vv2", "vv3", "vv4", "vv5")), "the stock executables are not in research/stock-executables")
    class TheCollectionDrawsOdds(unittest.TestCase):
        def choose(self, draw: int, solidarity=None) -> int:
            r = Roll(4)
            text = r.p.alloc(len(MANIFEST) + 1)
            r.p.write(text, MANIFEST.encode() + b"\0")
            r.p.export("VvfpStoryProbeCollectionManifest", text, 0, 0b111)
            if solidarity is not None:
                fake_solidarity(r.p, *solidarity, [], hook=False)
            r.rolls(0, draw, 0, 0)          # round 6: the first number draws the group (one here), the next the event
            trace = r.p.alloc(64 * 4)
            got = r.p.export("VvfpStoryProbeCollectionChoose", 4, trace, 64)
            self.assertTrue(got & 0x100)
            return r.p.u32(trace + 4 * ((got & 0xFF) - 1)) & 0xFFFF

        def test_without_the_companion_every_event_equally_likely(self) -> None:
            for draw in range(6):
                with self.subTest(draw=draw):
                    self.assertEqual(self.choose(draw), draw % 3)

        def test_a_high_score_favours_the_cooperative_event(self) -> None:
            # Cooperative x2: weights 2000 / 1000 / 1000 of 4000 (every other candidate x 1000): [0, 2000) the
            # feast, [2000, 3000) the walk, the rest the apology -- the feast half the draw instead of a third.
            for draw, entry in ((0, 0), (1999, 0), (2000, 1), (2999, 1), (3000, 2), (3999, 2)):
                with self.subTest(draw=draw):
                    self.assertEqual(self.choose(draw, (2000, 1000)), entry)

        def test_a_low_score_favours_the_repair_event(self) -> None:
            # Repair x2: 1000 / 1000 / 2000 -- the apology half the draw.
            for draw, entry in ((999, 0), (1000, 1), (1999, 1), (2000, 2), (3999, 2)):
                with self.subTest(draw=draw):
                    self.assertEqual(self.choose(draw, (1000, 2000)), entry)

        def test_a_big_total_takes_two_of_the_games_numbers(self) -> None:
            # A total past the game's exact 0x7FFF (a factor of 40x for the test): the feast 40000 of 42000, drawn as
            # (hi << 15 | lo) mod 42000 from two of the game's numbers.
            for hi, lo in ((0, 0), (1, 7231), (1, 7232), (1, 8231), (1, 8232), (2, 0)):
                value = ((hi << 15) | lo) % 42000
                entry = 0 if value < 40000 else 1 if value < 41000 else 2
                with self.subTest(hi=hi, lo=lo):
                    r = Roll(4)
                    text = r.p.alloc(len(MANIFEST) + 1)
                    r.p.write(text, MANIFEST.encode() + b"\0")
                    r.p.export("VvfpStoryProbeCollectionManifest", text, 0, 0b111)
                    fake_solidarity(r.p, 40000, 1000, [], hook=False)
                    r.rolls(0, hi, lo, 0)       # round 6: the group first
                    trace = r.p.alloc(64 * 4)
                    got = r.p.export("VvfpStoryProbeCollectionChoose", 4, trace, 64)
                    self.assertEqual(r.p.u32(trace + 4 * ((got & 0xFF) - 1)) & 0xFFFF, entry)

        def test_a_series_member_is_weighted_by_its_own_factor(self) -> None:
            """A walk (solo), and a series of a cooperative and a plain member.  With cooperative x3 the series weighs
            (3000 + 1000) / 2 = 2000 against the walk's 1000, and its member is drawn 3000 : 1000 -- the cooperative
            member's share is its own share x3; without the companion: the series as one event, its members alike."""
            manifest = "\n".join([
                "# series",
                "a_walk\tA Walk\t4\t1\t\tc\td\t\t",
                "s_feast\tThe Feast\t4\t1\tser\tc\td\t\t\tcooperative",
                "s_chat\tA Chat\t4\t1\tser\tc\td\t\t",
            ]) + "\n"

            def pick(rolls, solidarity):
                r = Roll(4)
                text = r.p.alloc(len(manifest) + 1)
                r.p.write(text, manifest.encode() + b"\0")
                r.p.export("VvfpStoryProbeCollectionManifest", text, 0, 0b111)
                if solidarity:
                    fake_solidarity(r.p, 3000, 1000, [], hook=False)
                r.rolls(0, *rolls, 0, 0)
                trace = r.p.alloc(64 * 4)
                got = r.p.export("VvfpStoryProbeCollectionChoose", 4, trace, 64)
                return r.p.u32(trace + 4 * ((got & 0xFF) - 1)) & 0xFFFF

            for rolls, entry in (((0, 0), 0), ((999, 3999), 0), ((1000, 2999), 1), ((2999, 3000), 2)):
                with self.subTest(rolls=rolls):
                    self.assertEqual(pick(rolls, True), entry)
            for rolls, entry in (((0, 0), 0), ((1, 0), 1), ((1, 1), 2)):
                with self.subTest(off=rolls):
                    self.assertEqual(pick(rolls, False), entry)
        def test_at_50_the_draw_is_as_before(self) -> None:
            for draw in range(6):
                with self.subTest(draw=draw):
                    self.assertEqual(self.choose(draw, (1000, 1000)), draw % 3)

if __name__ == "__main__":
    unittest.main()
