"""The Virtual Villagers side of translations: the string inventories, the generated site table, the feature
rows and the templates read from the stock games.

The parts that need a stock executable (inputs/vv<N>-stock-copy, gitignored) skip without one, as on CI.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_translation_format as fmt  # noqa: E402
import vv_translations as vt  # noqa: E402

GAMES = range(1, 6)


def stock_exe(number: int) -> Path:
    return ROOT / "inputs" / f"vv{number}-stock-copy" / f"{vt.TITLES[number]}.exe"


class InventoryFilesTests(unittest.TestCase):
    """No stock game needed."""

    def test_inventories_hold_no_english(self):
        for number in GAMES:
            with self.subTest(game=number):
                inv = vt.load_inventory(number)
                self.assertEqual(inv["title"], vt.TITLES[number])
                for row in inv["rows"]:
                    self.assertNotIn("english", row)
                    self.assertRegex(row["stem"], r"^(table|sm|exe)/[A-Za-z0-9_.\-/]+$")
                    self.assertRegex(row["stock_hash"], r"^[0-9a-f]{8}$")
                stems = [row["stem"] for row in inv["rows"]]
                self.assertEqual(len(stems), len(set(stems)))

    def test_patcher_strings_keys(self):
        strings = vt.load_patcher_strings()
        self.assertGreater(len(strings), 1000)
        stems = [s["stem"] for s in strings]
        self.assertEqual(len(stems), len(set(stems)))
        for s in strings:
            fmt.make_key(*s["stem"].split("/", 1), s["english"])          # raises on a bad key
            self.assertTrue(set(s["games"]) <= {"vv1", "vv2", "vv3", "vv4", "vv5"})
            self.assertFalse(fmt.find_emails(s["english"]), s["stem"])

    def test_sites_include_is_the_inventory(self):
        inc = (ROOT / "native" / "vvfp_translations" / "tr_sites.inc").read_text(encoding="utf-8")
        for number in GAMES:
            block = re.search(r"TR_SITES_VV%d\[\] = \{(.*?)\n\};" % number, inc, re.S).group(1)
            listed = {(int(lit, 16), int(site, 16)) for lit, site in
                      re.findall(r"\{ 0x([0-9A-F]+)u, 0x([0-9A-F]+)u", block)}
            inv = vt.load_inventory(number)
            expected = {(int(l["va"], 16), int(s, 16)) for l in inv["literals"] for s in l["sites"]}
            with self.subTest(game=number):
                self.assertEqual(listed, expected)

    def test_feature_rows_pin_the_dll(self):
        dll = ROOT / "assets" / "translations" / vt.DLL_NAME
        digest = hashlib.sha256(dll.read_bytes()).hexdigest().upper()
        for number in GAMES:
            with self.subTest(game=number):
                row = json.loads((ROOT / "data" / f"vv{number}_translations_feature.json").read_text(encoding="utf-8"))
                self.assertEqual(row["id"], f"vv{number}_translations")
                self.assertTrue(row["enabled"])
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["companion_files"],
                                 [{"source": "assets/translations/VVFP Translations.dll",
                                   "destination": "VVFP Translations.dll", "sha256": digest}])
                self.assertIn("**On by default, and English until you choose a language", row["description"])

    def test_startup_starts_the_companion(self):
        import vv_fun_patcher as vfp
        self.assertEqual(vfp.STARTUP_LOADER_COMPANIONS_2[-1], "VVFP Translations.dll")
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Translations.dll",', header)
        startup = ROOT / "assets" / "startup" / "VVFP Startup.dll"
        self.assertEqual(hashlib.sha256(startup.read_bytes()).hexdigest().upper(),
                         vfp.STARTUP_LOADER_COMPANION["sha256"])
        self.assertIn(b"VVFP Translations.dll", startup.read_bytes())

    def test_game_number(self):
        self.assertEqual(vt.game_number("vv3"), 3)
        self.assertEqual(vt.game_number(vt.TITLES[4]), 4)
        self.assertEqual(vt.game_number(5), 5)
        with self.assertRaises(ValueError):
            vt.game_number("Fish Tycoon")

    def test_release_ships_the_feature(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for path in ("assets/translations/VVFP Translations.dll", "src/vv_translation_format.py",
                     "src/vv_translations.py", "src/vv_translations_window.py",
                     "data/translations/patcher_strings.json", "docs/translation-file-format.md",
                     "docs/translating-the-games.md", *(f"data/vv{n}_translations_feature.json" for n in GAMES),
                     *(f"data/translations/vv{n}_strings.json" for n in GAMES)):
            with self.subTest(path=path):
                self.assertIn(f'"{path}"', release)
                self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn("TRANSLATION_FILES", release)


@unittest.skipUnless(all(stock_exe(n).is_file() for n in GAMES), "stock executables are not in inputs/")
class StockGameTests(unittest.TestCase):
    """The inventories match the stock games, and a template is the game's own English."""

    def test_stock_hashes_and_tables(self):
        for number in GAMES:
            with self.subTest(game=number):
                inv = vt.load_inventory(number)
                data = stock_exe(number).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest().upper(), inv["stock_exe_sha256"])
                english = vt.game_english(number, stock_exe(number))
                for row in inv["rows"]:
                    self.assertEqual(fmt.english_hash(english[row["stem"]]), row["stock_hash"], row["stem"])

    def test_literal_sites_are_stock_pushes(self):
        for number in GAMES:
            image = vt.ExeImage(stock_exe(number).read_bytes())
            for lit in vt.load_inventory(number)["literals"]:
                for site in lit["sites"]:
                    with self.subTest(game=number, site=site):
                        off = image.offset(int(site, 16))
                        b = image.data[off:off + 5]
                        self.assertTrue(b[0] == 0x68 or 0xB8 <= b[0] <= 0xBF)
                        self.assertEqual(int.from_bytes(b[1:5], "little"), int(lit["va"], 16))

    def test_template_from_the_stock_game(self):
        expected_min = {1: 600, 2: 850, 3: 1150, 4: 1300, 5: 1350}
        for number in GAMES:
            with self.subTest(game=number):
                rows = vt.template_rows(number, exe=stock_exe(number))
                game_rows = [r for r in rows if r.row.key.split("/")[0] in ("table", "sm", "exe")]
                self.assertGreaterEqual(len(game_rows), expected_min[number])
                keys = [r.row.key for r in rows]
                self.assertEqual(len(keys), len(set(keys)))
                tf = vt.new_translation(number, "Français", "fr", rows)
                report = fmt.validate(tf, vt.template_map(rows), vt.TITLES[number])
                self.assertFalse(report.file_errors)
                self.assertEqual(report.used, 0)
                self.assertEqual(report.total, len(rows))
                # A translated copy validates against the template, and the file round-trips.
                for row in tf.rows[:5]:
                    row.translation = row.english
                again = fmt.parse(fmt.dumps(tf))
                self.assertEqual(fmt.validate(again, vt.template_map(rows), vt.TITLES[number]).used, 5)

    def test_tabbed_names_are_keyed_without_the_tabs(self):
        for number in (3, 4, 5):
            with self.subTest(game=number):
                stems = {row["stem"] for row in vt.load_inventory(number)["rows"]}
                self.assertIn("sm/eSayApprentice", stems)

    def test_sm_xml_wins_over_the_built_in_english(self):
        sm = ROOT / "assets" / "text-changes" / "vv4-sm.xml"
        english = vt.game_english(4, stock_exe(4), sm)
        builtin = vt.game_english(4, stock_exe(4))
        self.assertNotEqual(english, builtin)          # Optional Text Changes rewrites some lines
        self.assertEqual(set(english), set(builtin))


if __name__ == "__main__":
    unittest.main()
