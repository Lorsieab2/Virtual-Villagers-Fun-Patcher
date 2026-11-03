"""The translation file format (src/vv_translation_format.py, docs/translation-file-format.md): game-neutral rules.

Nothing here needs a game: CI runs it everywhere.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_translation_format as fmt  # noqa: E402

TITLE = "Virtual Villagers - The Secret City"


def sample(translations: dict[str, str] | None = None) -> fmt.TranslationFile:
    rows = [
        fmt.Row(fmt.make_key("sm", "eHello", "Hello"), "Hello"),
        fmt.Row(fmt.make_key("sm", "eFound", "%s found %d apples."), "%s found %d apples.",
                notes="%1 = text (person); %2 = a number (number)"),
        fmt.Row(fmt.make_key("sm", "eName", "{name} is happy."), "{name} is happy."),
        fmt.Row(fmt.make_key("table", "12", "* found a crate."), "* found a crate.",
                notes="* = the villager's name (person)"),
    ]
    tf = fmt.template_file(rows, TITLE, "Français", "fr", "Test Translator")
    for row in tf.rows:
        row.translation = (translations or {}).get(row.english, "")
    return tf


class FileTests(unittest.TestCase):
    def roundtrip(self, tf: fmt.TranslationFile, encoding: str = "utf-8-sig") -> fmt.TranslationFile:
        data = fmt.dumps(tf).encode(encoding) if encoding != "utf-16" else fmt.dumps(tf).encode("utf-16")
        return fmt.parse(fmt.decode_bytes(data))

    def test_written_with_bom_and_read_back(self):
        tf = sample({"Hello": "Bonjour\tà tous\n\\ fin"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / fmt.file_name(TITLE, "Français")
            fmt.write_file(path, tf)
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            back = fmt.read_file(path)
        self.assertEqual(back.rows[0].translation, "Bonjour\tà tous\n\\ fin")
        self.assertEqual(back.language, "Français")
        self.assertEqual(back.code, "fr")
        self.assertEqual(back.game, TITLE)

    def test_every_encoding_the_spec_allows(self):
        tf = sample({"Hello": "Merhaba ğüşıöç 日本語 \U00012000"})
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le-bom", "utf-16-be-bom"):
            with self.subTest(encoding=encoding):
                text = fmt.dumps(tf)
                if encoding == "utf-16-le-bom":
                    data = b"\xff\xfe" + text.encode("utf-16-le")
                elif encoding == "utf-16-be-bom":
                    data = b"\xfe\xff" + text.encode("utf-16-be")
                else:
                    data = text.encode(encoding)
                back = fmt.parse(fmt.decode_bytes(data))
                self.assertEqual(back.rows[0].translation, "Merhaba ğüşıöç 日本語 \U00012000")

    def test_not_utf8_is_refused_whole(self):
        with self.assertRaises(fmt.FormatError):
            fmt.decode_bytes(fmt.dumps(sample()).encode("utf-8") + b"\xff\xfe\xfa")

    def test_oversized_and_headerless_are_refused(self):
        with self.assertRaises(fmt.FormatError):
            fmt.decode_bytes(b" " * (fmt.MAX_FILE_BYTES + 1))
        with self.assertRaises(fmt.FormatError):
            fmt.parse("just some text\n")

    def test_newer_format_is_refused(self):
        tf = sample()
        tf.set_info("@format", "2", "2")
        with self.assertRaises(fmt.FormatError):
            fmt.parse(fmt.dumps(tf))

    def test_spreadsheet_quotes_are_undone(self):
        tf = sample({"Hello": '"Bonjour" dit-il'})
        text = fmt.dumps(tf)
        self.assertIn('"""Bonjour"" dit-il"', text)
        self.assertEqual(fmt.parse(text).rows[0].translation, '"Bonjour" dit-il')

    def test_bad_row_is_an_issue_not_a_crash(self):
        text = fmt.dumps(sample()) + "not-a-key\tx\ty\r\n"
        tf = fmt.parse(text)
        self.assertEqual(len(tf.rows), 4)
        self.assertTrue(any("key is not well formed" in i.message for i in tf.issues))

    def test_keys(self):
        key = fmt.make_key("sm", "eHello", "Hello")
        self.assertEqual(fmt.split_key(key), ("sm", "eHello", fmt.english_hash("Hello")))
        self.assertEqual(fmt.key_stem(key), "sm/eHello")
        self.assertIsNone(fmt.split_key("sm/eHello"))
        with self.assertRaises(ValueError):
            fmt.make_key("SM", "x", "y")


class RowTests(unittest.TestCase):
    def errors(self, english, translation, rules=None):
        return [i.message for i in fmt.check_row(english, translation, rules) if i.severity == "error"]

    def test_printf_order_and_set(self):
        self.assertEqual(self.errors("%s found %d apples.", "%s a trouvé %d pommes."), [])
        self.assertTrue(self.errors("%s found %d apples.", "%d pommes, %s"))
        self.assertTrue(self.errors("%s found %d apples.", "%s a trouvé des pommes."))

    def test_percent_rules(self):
        # Only the tokens of the line's own English are placeholders (UNICODE_SPEC section 7): any other '%' is text.
        self.assertEqual(self.errors("Hello", "Bonjour 100%"), [])
        self.assertEqual(self.errors("%d%% done", "%d%% fait"), [])
        self.assertEqual(self.errors("%d done", "%d fait %"), [])

    def test_french_percent_with_a_space(self):
        for tr in ("50 % de réduction", "2 %", "2 %", "2 %"):
            with self.subTest(tr=tr):
                self.assertEqual(self.errors("Sale", tr), [])
                self.assertEqual(self.errors("%d left", "%d restants, " + tr), [])

    def test_a_conversion_the_english_lacks_is_text(self):
        # "% d" here is French "50 %" + "d...": not a printf placeholder, because the English has none
        self.assertEqual(fmt.translation_tokens("50 % de réduction", "Sale"), [])
        self.assertEqual(fmt.translation_tokens("%d sur 50 % de", "%d left"), ["%d"])

    def test_the_placeholders_of_the_english_are_still_required(self):
        self.assertTrue(self.errors("%d left", "restants"))
        self.assertTrue(self.errors("%d left", "%s restants"))
        self.assertEqual(self.errors("%d left", "%3d restants"), [])          # width may change
        self.assertTrue(self.errors("%d left", "% d restants"))               # never by the space flag alone

    def test_runtime_text_writes_double_percent_in_a_format_line(self):
        self.assertEqual(fmt.runtime_text("%d restants, 50 %", "%d left"), "%d restants, 50 %%")
        self.assertEqual(fmt.runtime_text("%d restants, 50 %%", "%d left"), "%d restants, 50 %%")   # old way kept
        self.assertEqual(fmt.runtime_text("%3d sur 50 %", "%d left"), "%3d sur 50 %%")
        # a line the program does not use as a format is handed on as it is
        self.assertEqual(fmt.runtime_text("50 % de réduction", "Sale"), "50 % de réduction")
        self.assertEqual(fmt.runtime_text("50 %", "Sale", is_format=True), "50 %%")
        # a select head's % is not a percent sign
        self.assertEqual(fmt.runtime_text("{%1: m=il | f=elle} a 50 %", "%s has 5 %%"), "{%1: m=il | f=elle} a 50 %%")

    def test_the_extra_percent_bytes_count_toward_the_room(self):
        rules = fmt.RowRules(byte_limit=len("%d ok, 50 %".encode()))
        self.assertTrue([i for i in fmt.check_row("%d ok", "%d ok, 50 %", rules) if i.severity == "error"])
        rules = fmt.RowRules(byte_limit=len("%d ok, 50 %%".encode()))
        self.assertFalse([i for i in fmt.check_row("%d ok", "%d ok, 50 %", rules) if i.severity == "error"])

    def test_double_percent_in_a_plain_line_is_warned(self):
        issues = fmt.check_row("Sale", "50 %% off")
        self.assertEqual([i.severity for i in issues], ["warning"])

    def test_named_variables(self):
        self.assertEqual(self.errors("{name} is happy.", "{name} est content."), [])
        self.assertTrue(self.errors("{name} is happy.", "Il est content."))
        self.assertTrue(self.errors("{name} is happy.", "{name} {nom} est content."))

    def test_gender_select(self):
        tr = "{name} est {name: m=content | f=contente | o=content·e}."
        self.assertEqual(self.errors("{name} is happy.", tr), [])
        self.assertEqual(fmt.render(tr, {"name": "f"}), "{name} est contente.")
        self.assertEqual(fmt.render(tr, {"name": "m"}), "{name} est content.")
        self.assertEqual(fmt.render(tr, {}), "{name} est content·e.")

    def test_two_people(self):
        english = "{actor} healed {target}."
        tr = "{actor} a soigné {target: m=son fils | f=sa fille | o=son enfant} {target} ; {actor: m=il | f=elle} est fier."
        self.assertEqual(self.errors(english, tr), [])
        self.assertEqual(fmt.render(tr, {"actor": "f", "target": "m"}),
                         "{actor} a soigné son fils {target} ; elle est fier.")
        # A select chooses words by its subject; it never stands in for the subject itself.
        self.assertTrue(self.errors(english, "{actor} a soigné {target: m=son fils | f=sa fille}."))

    def test_missing_branch_fallback(self):
        sel = fmt.parse_selects("{x: o=iel}")[0]
        self.assertEqual(fmt.choose(sel, "m"), "iel")
        sel = fmt.parse_selects("{x: f=elle | m=il}")[0]
        self.assertEqual(fmt.choose(sel, "o"), "elle")          # no o: the first branch written
        sel = fmt.parse_selects("{n: one=pomme}")[0]
        self.assertEqual(fmt.choose(sel, 5), "pomme")

    def test_plural_select_on_printf(self):
        english = "%d apples"
        tr = "%d {%1: one=pomme | other=pommes}"
        self.assertEqual(self.errors(english, tr), [])
        self.assertEqual(fmt.render(tr, {"%1": 0}, "fr"), "%d pomme")
        self.assertEqual(fmt.render(tr, {"%1": 2}, "fr"), "%d pommes")
        tr_pl = "%d {%1: one=plik | few=pliki | many=plików}"
        self.assertEqual([fmt.render(tr_pl, {"%1": n}, "pl") for n in (1, 3, 5, 22, 25)],
                         ["%d plik", "%d pliki", "%d plików", "%d pliki", "%d plików"])
        self.assertEqual(fmt.render("{%1: =0=aucune | one=une | other=plusieurs}", {"%1": 0}, "fr"), "aucune")

    def test_malformed_selects(self):
        for bad in ("{%1: m=il | f=elle", "{%1: x=il}", "{%1: m=il | m=lui}", "{%1: m=%d}",
                    "{%1: m=il | one=un}", "{%1: m=a {%1: f=b}}", "{%1: m}"):
            with self.subTest(bad=bad):
                self.assertTrue(self.errors("%s ok", "%s " + bad))

    def test_select_subject_must_exist_and_match_kind(self):
        self.assertTrue(self.errors("%s ok", "%s {%2: m=a | f=b}"))
        self.assertTrue(self.errors("%d ok", "%d {%1: m=a | f=b}"))
        self.assertTrue(self.errors("Hello", "{who: m=Salut | f=Salut}"))
        rules = fmt.RowRules(subjects={"*": "person"})
        self.assertEqual(self.errors("* is here", "* est {*: m=là | f=là}", rules), [])

    def test_game_tokens(self):
        rules = fmt.RowRules(subjects={"*": "person"}, tokens=tuple("*^&+="), required_tokens=("*",),
                             forbid_chars="*^&+=")
        self.assertEqual(self.errors("* found it", "* l'a trouvé", rules), [])
        self.assertTrue(self.errors("* found it", "Il l'a trouvé", rules))
        self.assertTrue(self.errors("* found it", "* l'a trouvé + ^", rules))

    def test_emails_anywhere_are_refused(self):
        self.assertTrue(self.errors("Hello", "Bonjour, écrivez à jean.dupont@example.fr"))
        tf = sample({"Hello": "Bonjour"})
        tf.set_info("@translator", "", "me@example.com")
        self.assertTrue(fmt.validate(tf).file_errors)
        tf = sample({"Hello": "Bonjour"})
        tf.comments.append("# contact: someone @ example . org")
        self.assertTrue(fmt.validate(tf).file_errors)

    def test_cuneiform_cjk_turkish_are_plain_text(self):
        for text in ("Merhaba dünya, ğüşıİ", "你好，村民", "こんにちは", "\U00012000\U00012001\U00012002"):
            with self.subTest(text=text):
                self.assertEqual(self.errors("Hello", text), [])


class ReportTests(unittest.TestCase):
    def test_validate_without_template(self):
        tf = sample({"Hello": "Bonjour", "%s found %d apples.": "%d %s"})
        report = fmt.validate(tf)
        self.assertEqual(report.total, 4)
        self.assertEqual(report.translated, 2)
        self.assertEqual(report.used, 1)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(round(report.coverage), 25)

    def test_edited_english_column_is_an_error(self):
        tf = sample({"Hello": "Bonjour"})
        tf.rows[0].english = "Hi"
        report = fmt.validate(tf)
        self.assertTrue(any("English column was edited" in i.message for i in report.errors))

    def test_validate_against_template_stale_unknown_missing(self):
        tf = sample({"Hello": "Bonjour"})
        template = {fmt.make_key("sm", "eHello", "Hello there"): ("Hello there", None),
                    fmt.make_key("sm", "eNew", "New"): ("New", None)}
        report = fmt.validate(tf, template)
        self.assertEqual([r.key for r in report.stale], [tf.rows[0].key])
        self.assertEqual(len(report.unknown), 3)
        self.assertEqual(len(report.missing), 2)
        self.assertEqual(report.used, 0)

    def test_update_keeps_marks_and_adds(self):
        tf = sample({"Hello": "Bonjour", "{name} is happy.": "{name} est content."})
        rows = [fmt.Row(fmt.make_key("sm", "eHello", "Hello"), "Hello"),
                fmt.Row(fmt.make_key("sm", "eName", "{name} is glad."), "{name} is glad."),
                fmt.Row(fmt.make_key("sm", "eBrand", "Brand new"), "Brand new")]
        new, status = fmt.update(tf, rows)
        self.assertEqual([status[r.key] for r in rows], ["kept", "changed", "new"])
        self.assertEqual(new.rows[0].translation, "Bonjour")
        self.assertEqual(new.rows[1].translation, "")
        self.assertIn("old translation: {name} est content.", new.rows[1].notes)

    def test_wrong_game_is_refused(self):
        tf = sample({"Hello": "Bonjour"})
        self.assertTrue(fmt.check_info(tf, "Virtual Villagers - New Believers"))
        self.assertFalse(fmt.check_info(tf, TITLE))

    def test_file_name(self):
        self.assertEqual(fmt.file_name(TITLE, "Français"), "Virtual Villagers - The Secret City - Français.txt")
        self.assertEqual(fmt.file_name(TITLE, 'a/b:c'), "Virtual Villagers - The Secret City - a_b_c.txt")

    def test_plural_tables(self):
        self.assertEqual(fmt.plural_categories("en"), ["one", "other"])
        self.assertEqual(fmt.plural_categories("ja"), ["other"])
        self.assertEqual(fmt.plural_categories("ru"), ["one", "few", "many"])
        self.assertEqual(fmt.plural_categories("ar"), ["zero", "one", "two", "few", "many", "other"])
        self.assertEqual(fmt.plural_category("fr", 0), "one")
        self.assertEqual(fmt.plural_category("tr", 0), "other")
        self.assertEqual(fmt.plural_category("xx-unknown", 1), "one")
        for name in set(fmt.PLURAL_RULE_OF.values()):
            self.assertIn(name, fmt.PLURAL_RULES)

    def test_language_list(self):
        codes = [code for code, _native, _english in fmt.LANGUAGES]
        self.assertEqual(len(codes), len(set(codes)))
        for must in ("fr", "tr", "ja", "zh-Hans", "akk"):
            self.assertIn(must, codes)


if __name__ == "__main__":
    unittest.main()
