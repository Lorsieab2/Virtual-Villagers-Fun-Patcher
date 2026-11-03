"""Every patch's own text is translatable (the owner, 2026-11-02: "FOR ALL TRANSLATIONS AND ALL GAMES PLEASE ADD
THE ABILITY TO SUPPORT EVERY SINGLE PATCH!!!!").

* Every player-visible string scripts/scan_patch_text.py finds in the shipped companions' C sources (string
  literals read with C's own rules: adjacent literals joined, escapes decoded; a candidate reads as words) is in
  the "Make a translation" template (data/translations/patcher_strings.json, which vv_translations.template_rows
  adds to each game's template) or matched by a listed exclusion with its reason
  (data/translations/patch_text_exclusions.json).
* Every text an exe patch writes (each NUL-terminated text run of an "after" block in data/'s feature and build
  JSONs that differs from its "before") is listed in data/translations/exe_patch_strings.json with the template
  row that covers it.
* Every key a companion asks "VVFP Translations.dll" for (native/shared/vvfp_translate.h) is a template row whose
  English is the English the companion passes.

No stock game is needed: this runs on CI.
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import scan_patch_text as scan  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as vt  # noqa: E402

GAMES = {f"vv{n}" for n in range(1, 6)}


def patcher_rows() -> list[dict]:
    return vt.load_patcher_strings()


class CompanionTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = patcher_rows()
        cls.english = {r["english"] for r in cls.rows}
        cls.rules = scan.load_exclusions()
        cls.candidates = scan.c_candidates()

    def test_the_scan_reads_the_sources(self) -> None:
        self.assertGreater(len(self.candidates), 3000)
        files = {c.file.split("/")[1] for c in self.candidates}
        for folder in ("vvfp_story_upgrades", "vv1_origins_icons", "vvfp_cause_of_death", "vv1_parentage",
                       "vvfp_vv3_both_factions", "vvfp_storytelling", "shared"):
            self.assertIn(folder, files)
        joined = [c for c in self.candidates if c.text.startswith("With the power of the Fun Patcher,\n")]
        self.assertEqual(joined[0].text.count("\n"), 4)              # adjacent literals joined, as C joins them

    def test_every_visible_string_is_in_the_template_or_excluded(self) -> None:
        missing = [c for c in self.candidates if c.text not in self.english and not scan.excluded_by(c, self.rules)]
        listed = "\n".join(f"{c.file}:{c.line} ({c.context}) {c.text!r}" for c in missing[:40])
        self.assertEqual(missing, [], "strings missing from the Make a translation template "
                                      "(add them with scripts/build_patch_text_inventory.py, or exclude them in "
                                      f"data/translations/patch_text_exclusions.json with a reason):\n{listed}")

    def test_every_exclusion_has_a_reason_and_is_used(self) -> None:
        patch_texts = scan.patch_texts()
        for rule in self.rules:
            with self.subTest(reason=rule.get("reason", "")[:60]):
                self.assertGreater(len(rule.get("reason", "")), 20)
                used = any(scan.excluded_by(c, [rule]) for c in self.candidates) or any(
                    scan.patch_excluded_by(p, [rule]) for p in patch_texts)
                self.assertTrue(used, "an exclusion that matches nothing")

    def test_no_excluded_string_is_translated(self) -> None:
        """An excluded string (a log line, a file name) is never given a template row of its own: the template and
        the exclusions do not overlap unless the same words also show somewhere."""
        excluded_only = {c.text for c in self.candidates if scan.excluded_by(c, self.rules)} - {
            c.text for c in self.candidates if not scan.excluded_by(c, self.rules)}
        names = {"Joey", "Joey Joerson", "Unknown"}
        self.assertFalse(names & {r["english"] for r in self.rows if r["stem"].startswith("vvfp.story/")
                                  and ("JOEY" in r["stem"] or "conceive" in r["stem"])})
        self.assertTrue(excluded_only)

    def test_rows_are_well_formed(self) -> None:
        stems = [r["stem"] for r in self.rows]
        self.assertEqual(len(stems), len(set(stems)))
        for row in self.rows:
            with self.subTest(stem=row["stem"]):
                fmt.make_key(*row["stem"].split("/", 1), row["english"])
                self.assertTrue(row["games"] and set(row["games"]) <= GAMES)
                self.assertIn(row["mechanism"], ("a", "b", "d", "e"))


class ExePatchTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = {r["stem"]: r for r in patcher_rows()}
        cls.listed = json.loads((ROOT / "data" / "translations" / "exe_patch_strings.json").read_text(
            encoding="utf-8"))["texts"]
        cls.rules = scan.load_exclusions()

    def test_every_exe_patch_text_is_covered(self) -> None:
        index = {(t["file"], int(t["offset"], 16), t["english"]): t for t in self.listed}
        found = [p for p in scan.patch_texts() if not scan.patch_excluded_by(p, self.rules)]
        self.assertGreater(len(found), 40)
        for item in found:
            with self.subTest(file=item.file, offset=hex(item.offset)):
                entry = index.get((item.file, item.offset, item.text))
                self.assertIsNotNone(entry, f"{item.text!r} is not in exe_patch_strings.json "
                                            "(scripts/build_patch_text_inventory.py)")
                covered = entry["covered_by"]
                if covered.startswith(("patch/", "vvfp.exepatch/")):
                    self.assertEqual(self.rows[covered]["english"], item.text)
                    self.assertIn(f"vv{item.game}", self.rows[covered]["games"])
                else:
                    # The game's own string, rewritten in place: its table / sm / exe row reads the patched
                    # English from the player's patched game.
                    inv = vt.load_inventory(item.game)
                    self.assertIn(covered, {r["stem"] for r in inv["rows"]})

    def test_patch_rows_are_in_the_template_with_a_byte_limit(self) -> None:
        patch_rows = [r for r in self.rows.values() if r["stem"].startswith("patch/")]
        self.assertGreater(len(patch_rows), 20)
        for row in patch_rows:
            self.assertRegex(row["stem"], r"^patch/0x[0-9a-f]{5,7}(\.v\d+)?$")


class KeyLookupTests(unittest.TestCase):
    """Every vvfp_tr / vvfp_trf / ce_tr_printf call names a template row and passes that row's English."""

    CALL = re.compile(r'(?:vvfp_tr|ce_tr_printf\([^;]*?|vvfp_trf)\(?\s*"((?:vvfp|patch)[\w.\-]*/[\w.\-%]+)",\s*'
                      r'"((?:[^"\\]|\\.)*)"', re.S)

    def test_every_key_a_companion_asks_for_exists(self) -> None:
        rows = {r["stem"]: r for r in patcher_rows()}
        seen = 0
        for path, relative in scan.source_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in self.CALL.finditer(text):
                stem, english = m.group(1), scan._decode(m.group(2), False)
                seen += 1
                with self.subTest(file=relative, stem=stem):
                    if "%d" in stem:
                        prefix = stem.split("%d")[0]
                        self.assertTrue(any(s.startswith(prefix) for s in rows), stem)
                        continue
                    self.assertIn(stem, rows)
                    self.assertEqual(rows[stem]["english"], english)
        self.assertGreaterEqual(seen, 15)

    def test_the_numbered_keys_exist(self) -> None:
        rows = {r["stem"]: r["english"] for r in patcher_rows()}
        source = (ROOT / "native" / "vvfp_cause_of_death" / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        words = re.search(r"CAUSE_WORDS\[7\] = \{(.*?)\};", source, re.S).group(1)
        for n, word in enumerate(re.findall(r'"([^"]*)"', words)):
            self.assertEqual(rows[f"vvfp.cod/vvfp_cause_of_death.CAUSE_WORDS.{n}"], word)
        epitaphs = re.search(r"EPITAPHS\[EPITAPH_COUNT\] = \{(.*?)\};", source, re.S).group(1)
        for n, word in enumerate(re.findall(r'"([^"]*)"', epitaphs), start=1):
            self.assertEqual(rows[f"vvfp.cod/vvfp_cause_of_death.EPITAPHS.{n}"], word)
        for game in range(1, 6):
            for k in range(43, 47):
                self.assertIn(f"vvfp.story/story_c{game}.C{game}_ADAPTER.{k}", rows)
        custom = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        words = re.search(r"CE_WHY_WORDS\[CE_WHY_COUNT\] = \{(.*?)\};", custom, re.S).group(1)
        for n, word in enumerate(re.findall(r'"([^"]*)"', words)):
            self.assertEqual(rows[f"vvfp.story/story_custom.CE_WHY_WORDS.{n}"], word)


class CountsTests(unittest.TestCase):
    def test_every_game_has_patch_rows(self) -> None:
        counts = collections.Counter(g for r in patcher_rows() for g in r["games"])
        for game in sorted(GAMES):
            self.assertGreater(counts[game], 500, game)


if __name__ == "__main__":
    unittest.main()
