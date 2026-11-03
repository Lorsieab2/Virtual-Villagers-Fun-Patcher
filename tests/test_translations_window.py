"""The Translations window (src/vv_translations_window.py): the Language list, the editor, Add / Export and
Share on GitHub.

Everything runs in a temporary folder (the translations folder is patched to one); no game is started and no
game folder or save of the player's is read or written.  The window tests skip when Tk cannot start.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_how_to_use  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as tr  # noqa: E402
import vv_translations_window as w  # noqa: E402

GAME = 3
TITLE = tr.TITLES[GAME]

OWNER_PROMPT = (
    "This button allows you to share your game translation to the patcher's Public Github. IF ACCEPTED, everyone "
    "who uses this patcher will be able to see your translation in the game and your username will be included "
    "in the credits. Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!\n"
    "\n"
    "Email addresses are never saved and are rejected from translation files.\n"
    "\n"
    "This feature is meant to be a community collaboration tool for game modding only.\n"
    "\n"
    "You will need a Github account to proceed. Continue?"
)


def template_rows() -> list[tr.TemplateRow]:
    texts = [("eFood", "Food: %d"), ("eHello", "Hello"), ("eBaby", "{name} had a baby")]
    return [tr.TemplateRow(fmt.Row(fmt.make_key("sm", ident, english), english), fmt.RowRules())
            for ident, english in texts]


def write_translation(path: Path, language="Français", code="fr", translator="", game=TITLE,
                      translations=("Nourriture : %d", "", "")) -> Path:
    rows = template_rows()
    tf = fmt.template_file([r.row for r in rows], game, language, code, translator)
    for row, text in zip(tf.rows, translations):
        row.translation = text
    fmt.write_file(path, tf)
    return path


class TempTranslations(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="vvfp-tr-window-"))
        for name, value in (("TRANSLATIONS_DIR", self.temp / "Installed translations"),
                            ("LEGACY_DIR", self.temp / "translations")):
            patcher = mock.patch.object(tr, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(tr._display_choice.clear)
        self.addCleanup(tr._display_cache.clear)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)


# ---- the words -------------------------------------------------------------------------------------------------

class WordsTests(unittest.TestCase):
    def test_the_share_question_is_the_owners_text_verbatim(self) -> None:
        self.assertEqual(w.SHARE_PROMPT, OWNER_PROMPT)
        please = w.SHARE_PROMPT.index("Please DO NOT put ANY PRIVATE DETAILS")
        email = w.SHARE_PROMPT.index(fmt.EMAIL_SENTENCE)
        self.assertLess(please, email)
        self.assertEqual(w.SHARE_PROMPT[please:email].count("\n\n"), 1)   # the very next paragraph

    def test_the_sharing_lines(self) -> None:
        self.assertEqual(w.SHARE_SENTENCE, "If you want to share your translation, consider going to the "
                                           "Patcher's GitHub page and adding it!")
        self.assertEqual(w.SHARE_HOW, "How: press Share on GitHub..., drag the file in, press Submit.")

    def test_the_email_sentence_is_in_the_guide_and_the_credit_hint(self) -> None:
        self.assertIn(fmt.EMAIL_SENTENCE, w.CREDIT_HINT)
        self.assertIn(fmt.EMAIL_SENTENCE, vv_how_to_use.guide("translations").lines)
        guide = " ".join(vv_how_to_use.guide("translations").lines)
        for step in ("Make a translation", "Add translation file...", "Export...", "Delete...", "Recycle Bin",
                     "Select All", "Ctrl+click", "Shift+click", "Ctrl+A", "Share on GitHub...", "Translations row"):
            self.assertIn(step, guide)

    def test_the_tools_tab_has_the_button_in_both_boxes_with_a_guide(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        body = source[source.index("    def _build_tools_tab("):source.index("    def _copy_single_slot(")]
        self.assertIn('slot_links, "Translations...", self._translations_single', body)
        self.assertIn('_help_button(slot_links, "translations")', body)
        self.assertIn("vv_translations_window.open_translations(self, None)", body)
        self.assertIn('_help_button(slot_tools, "translations")', body)
        load = source[source.index("    def _load_settings("):source.index("    def _save_settings(")]
        save = source[source.index("    def _save_settings("):source.index("    def _browse_exe(")]
        self.assertIn("vv_translations_window.SETTINGS_KEY", load)
        self.assertIn("vv_translations_window.SETTINGS_KEY", save)


# ---- sharing -----------------------------------------------------------------------------------------------------

class CreditTests(unittest.TestCase):
    def test_an_empty_credit_is_refused(self) -> None:
        for name in ("", "   ", "\t"):
            self.assertIsNotNone(w.credit_problem(name))

    def test_an_email_like_credit_is_refused(self) -> None:
        for name in ("someone@example.com", "someone @ example . com", "Kai (kai@mail.org)", "kai@home"):
            problem = w.credit_problem(name)
            self.assertIsNotNone(problem, name)
        self.assertIn(fmt.EMAIL_SENTENCE, w.credit_problem("someone@example.com"))

    def test_a_typed_name_is_accepted(self) -> None:
        self.assertIsNone(w.credit_problem("Kalani of the Isle"))
        self.assertIsNone(w.credit_problem("Ålfrún 日本"))


class ShareUrlTests(unittest.TestCase):
    def test_the_address_has_the_form_fields_and_nothing_personal(self) -> None:
        url = w.share_url(TITLE, "Français", "fr", 42.4)
        self.assertTrue(url.startswith("https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/new?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["template"], ["translation.yml"])
        self.assertEqual(query["title"], [f"Translation: {TITLE} - Français"])
        self.assertEqual(query["game"], [TITLE])
        self.assertEqual(query["language"], ["Français"])
        self.assertEqual(query["code"], ["fr"])
        self.assertEqual(query["coverage"], ["42%"])
        self.assertNotIn("credit", query)
        self.assertNotIn("@", urllib.parse.unquote(url))
        self.assertNotIn(" ", url)


class ShareTests(TempTranslations):
    def setUp(self) -> None:
        super().setUp()
        folder = tr.game_dir(GAME)
        folder.mkdir(parents=True)
        self.path = write_translation(folder / w.export_name(GAME, "Français"))
        self.calls: list = []
        self.out = self.temp / "out"
        self.out.mkdir()

    def record(self, what, value=None):
        def call(*args):
            self.calls.append((what, args))
            return value
        return call

    def share(self, answer: bool, credit="Kalani"):
        with mock.patch.object(w.subprocess, "Popen") as popen, mock.patch.object(w.webbrowser, "open") as web, \
                mock.patch.object(w.messagebox, "showerror") as error:
            result = w.share_on_github(
                None, GAME, self.path, ask=self.record("ask", answer), ask_credit=self.record("credit", credit),
                choose_folder=self.record("folder", self.out), reveal=self.record("reveal"),
                browse=self.record("browse"))
        return result, popen, web, error

    def test_no_does_nothing_at_all(self) -> None:
        before = self.path.read_bytes()
        result, popen, web, _error = self.share(False)
        self.assertIsNone(result)
        self.assertEqual([c[0] for c in self.calls], ["ask"])
        self.assertEqual(self.calls[0][1][1:], (w.SHARE_TITLE, w.SHARE_PROMPT))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertFalse(w.export_dir().exists())
        popen.assert_not_called()
        web.assert_not_called()

    def test_the_question_uses_the_no_default_dialog(self) -> None:
        source = Path(w.__file__).read_text(encoding="utf-8")
        body = source[source.index("def share_on_github("):source.index("# ---- drag and drop")]
        self.assertIn("ask = ask or vv_copy_slot_window.ask_yes_no", body)
        self.assertLess(body.index("if not ask(parent, SHARE_TITLE, SHARE_PROMPT)"), body.index("(ask_credit or ask_credit_name)"))

    def test_a_refused_credit_writes_nothing(self) -> None:
        before = self.path.read_bytes()
        for credit in (None, "", "me@example.com"):
            self.calls.clear()
            result, popen, web, _error = self.share(True, credit)
            self.assertIsNone(result)
            self.assertNotIn("folder", [c[0] for c in self.calls])
            self.assertEqual(self.path.read_bytes(), before)
            popen.assert_not_called()
            web.assert_not_called()

    def test_yes_credits_exports_shows_and_opens_the_page(self) -> None:
        result, _popen, _web, error = self.share(True, "  Kalani  ")
        error.assert_not_called()
        self.assertEqual(result, self.out / f"{TITLE} - Français.txt")
        self.assertTrue(result.is_file())
        self.assertEqual(fmt.read_file(result).translator, "Kalani")
        self.assertEqual(fmt.read_file(self.path).translator, "Kalani")
        steps = [c[0] for c in self.calls]
        self.assertEqual(steps, ["ask", "credit", "folder", "reveal", "browse"])
        self.assertEqual(self.calls[3][1], (result,))
        url = self.calls[4][1][0]
        self.assertNotIn("Kalani", urllib.parse.unquote(url))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["code"], ["fr"])
        self.assertEqual(query["game"], [TITLE])

    def test_a_file_with_an_email_is_not_shared(self) -> None:
        write_translation(self.path, translations=("Écrivez à moi@example.com", "", ""))
        result, popen, web, error = self.share(True, "Kalani")
        self.assertIsNone(result)
        error.assert_called_once()
        self.assertEqual(list(self.out.iterdir()), [])
        web.assert_not_called()


# ---- the Language list, Add, Export ---------------------------------------------------------------------------

class FilesTests(TempTranslations):
    def test_export_file_name(self) -> None:
        self.assertEqual(w.export_name(GAME, "Français"), "Virtual Villagers - The Secret City - Français.txt")
        source = write_translation(self.temp / "mine.txt")
        target = w.export_translation(source, self.temp / "elsewhere" / w.export_name(GAME, "Français"))
        self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_add_refuses_a_file_with_an_email(self) -> None:
        for translations in (("Nourriture : %d", "Bonjour moi@example.com", ""), ("", "", "")):
            path = write_translation(self.temp / "mail.txt", translations=translations,
                                     translator="x@y.com" if not translations[0] else "")
            installed, checked = w.add_translation(GAME, path)
            self.assertIsNone(installed)
            self.assertFalse(checked.ok)
            self.assertIn(fmt.EMAIL_SENTENCE, w.report_text(checked))
        self.assertEqual(tr.installed(GAME), [])

    def test_add_refuses_a_file_for_another_game(self) -> None:
        path = write_translation(self.temp / "other.txt", game=tr.TITLES[4])
        installed, checked = w.add_translation(GAME, path)
        self.assertIsNone(installed)
        self.assertTrue(any("not" in p and TITLE in p for p in checked.refused))
        self.assertEqual(tr.installed(GAME), [])

    def test_add_installs_a_good_file_and_reports_its_bad_lines(self) -> None:
        path = write_translation(self.temp / "good.txt", translator="Kalani",
                                 translations=("Nourriture : %d", "Bonjour {nom}", ""))
        installed, checked = w.add_translation(GAME, path, tr.template_map(template_rows()))
        self.assertEqual(installed, tr.game_dir(GAME) / "fr.tsv")
        self.assertTrue(checked.ok)
        text = w.report_text(checked)
        self.assertIn("33%", text)
        self.assertIn("stay English", text)
        self.assertEqual([i.label for i in tr.installed(GAME)], ["Français, by Kalani"])

    def test_patched_folders_found_from_what_the_patcher_knows(self) -> None:
        originals = self.temp / "games" / TITLE
        originals.mkdir(parents=True)
        modded = self.temp / "games" / f"{TITLE} - Modded"
        (modded / tr.PATCHER_FILES).mkdir(parents=True)
        unpatched = self.temp / "games" / f"{TITLE} - Modded 256"
        unpatched.mkdir()
        app = SimpleNamespace(all_folder_vars={"vv3": SimpleNamespace(get=lambda: str(originals))},
                              exe_var=SimpleNamespace(get=lambda: ""), last_modified_paths={},
                              translation_choices={})
        self.assertEqual(w.patched_folders(app, GAME), [modded])
        self.assertEqual(w.patched_folders(app, 4), [])


# ---- Tk ------------------------------------------------------------------------------------------------------

def _tk_root():
    # On this machine a fresh Tk now and then cannot read its own library files once ("couldn't read file
    # .../tk8.6/tk.tcl"); a second try works.  No display at all (CI) fails every time and skips.
    for attempt in range(4):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            return root
        except Exception as exc:  # noqa: BLE001 -- no display (CI)
            _tk_root.error = repr(exc)[:200]
            time.sleep(0.2 * (attempt + 1))
    return None


class TkCase(TempTranslations):
    def setUp(self) -> None:
        super().setUp()
        self.root = _tk_root()
        if self.root is None:
            self.skipTest(f"no Tk display ({getattr(_tk_root, 'error', '')})")
        self.addCleanup(self._destroy)

    def _destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass

    def pump(self, seconds: float = 0.0) -> None:
        end = time.monotonic() + seconds
        while True:
            self.root.update()
            if time.monotonic() >= end:
                break
            time.sleep(0.02)


class CreditBoxTests(TkCase):
    def test_nothing_is_pre_filled_and_bad_names_are_refused(self) -> None:
        with mock.patch.dict(os.environ, {"USERNAME": "WindowsUser", "USER": "WindowsUser"}):
            top, entry, answer = w.build_credit(self.root)
        self.pump()
        self.assertEqual(entry.get(), "")
        self.assertEqual(top.name_var.get(), "")
        top.ok_button.invoke()
        self.assertTrue(top.winfo_exists())
        self.assertIn("cannot be left empty", top.problem_var.get())
        self.assertIsNone(answer["name"])
        entry.insert(0, "kai@example.com")
        top.ok_button.invoke()
        self.assertTrue(top.winfo_exists())
        self.assertIn(fmt.EMAIL_SENTENCE, top.problem_var.get())
        self.assertIsNone(answer["name"])
        entry.delete(0, "end")
        entry.insert(0, "Kalani")
        top.ok_button.invoke()
        self.assertEqual(answer["name"], "Kalani")

    def test_the_share_question_has_no_as_its_default(self) -> None:
        dialogs = w.vv_copy_slot_window
        top, answer = dialogs.build_yes_no(self.root, w.SHARE_TITLE, w.SHARE_PROMPT)
        self.pump()
        labels = [c.cget("text") for c in top.winfo_children()[0].winfo_children() if c.winfo_class() == "TLabel"]
        self.assertEqual(labels, [OWNER_PROMPT])
        self.assertEqual(str(top.no_button.cget("default")), "active")
        top.event_generate("<Return>")
        self.pump()
        self.assertFalse(answer["yes"])

    def test_the_hint_says_emails_are_never_saved(self) -> None:
        top, _entry, _answer = w.build_credit(self.root)
        texts = [c.cget("text") for c in top.winfo_children()[0].winfo_children() if c.winfo_class() == "TLabel"]
        self.assertIn(w.CREDIT_HINT, texts)
        top.destroy()


def fake_app(root, patched: Path):
    """The Tk root dressed as the patcher: its five games, the folders it knows and its settings."""
    import tkinter as tk
    root.builds = [SimpleNamespace(id=f"vv{n}", title=t) for n, t in sorted(tr.TITLES.items())]
    root.all_folder_vars = {b.id: tk.StringVar(master=root) for b in root.builds}
    root.exe_var = tk.StringVar(master=root)
    root.status_var = tk.StringVar(master=root)
    root.last_modified_paths = {"vv3": patched}
    root.translation_choices = {}
    root.saved = 0

    def save() -> None:
        root.saved += 1

    root._save_settings = save
    return root


class WindowTests(TkCase):
    def setUp(self) -> None:
        super().setUp()
        self.patched = self.temp / "games" / f"{TITLE} - Modded"
        (self.patched / tr.PATCHER_FILES).mkdir(parents=True)
        self.app = fake_app(self.root, self.patched)
        for patch in (mock.patch.object(w, "_win_api", side_effect=OSError("no drag and drop in tests")),
                      mock.patch.object(w.messagebox, "showinfo"), mock.patch.object(w.messagebox, "showerror")):
            patch.start()
            self.addCleanup(patch.stop)

    def open(self) -> w.TranslationsWindow:
        top = w.open_translations(self.app, self.app.builds[GAME - 1])
        self.pump()
        return top.translations

    def test_add_then_choose_copies_the_file_and_english_removes_it(self) -> None:
        window = self.open()
        self.assertEqual(window.language_labels(), [tr.ENGLISH])
        self.assertEqual(window.drop_var.get(), "")              # no drag and drop: the button only
        good = write_translation(self.temp / "drop.txt", translator="Kalani")
        added = window.add_paths([str(good)])
        self.assertEqual(len(added), 1)
        self.assertEqual(window.language_labels(), [tr.ENGLISH, "Français, by Kalani"])
        runtime = tr.runtime_path(self.patched)
        self.assertFalse(runtime.exists())
        done = window.choose(1)
        self.assertEqual(done, [self.patched])
        self.assertEqual(runtime.read_bytes(), added[0].read_bytes())
        self.assertEqual(self.app.translation_choices["vv3"]["file"], "installed/fr.tsv")
        self.assertGreaterEqual(self.app.saved, 1)
        settings = repr(self.app.translation_choices)
        self.assertNotIn("Kalani", settings)                     # the credit is never in the settings
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Nourriture : %d")
        window.choose(0)
        self.assertFalse(runtime.exists())
        self.assertEqual(self.app.translation_choices["vv3"]["file"], "")
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Food: %d")
        window.close()

    def test_add_refuses_bad_files_in_the_window(self) -> None:
        window = self.open()
        bad = write_translation(self.temp / "bad.txt", translations=("moi@example.com", "", ""))
        other = write_translation(self.temp / "other.txt", game=tr.TITLES[2], language="Deutsch", code="de")
        self.assertEqual(window.add_paths([str(bad), str(other)]), [])
        self.assertEqual(window.language_labels(), [tr.ENGLISH])
        self.assertEqual(w.messagebox.showerror.call_count, 2)
        window.close()

    def test_choosing_with_no_patched_game_asks_for_the_folder(self) -> None:
        self.app.last_modified_paths = {}
        window = self.open()
        window.add_paths([str(write_translation(self.temp / "t.txt"))])
        with mock.patch.object(w.filedialog, "askdirectory", return_value=str(self.patched)) as ask:
            done = window.choose(1)
        ask.assert_called_once()
        self.assertEqual(done, [self.patched])
        self.assertTrue(tr.runtime_path(self.patched).is_file())
        self.assertEqual(self.app.translation_choices["vv3"]["folders"], [str(self.patched)])
        window.close()

    def test_make_opens_the_editor_on_a_new_file_and_saving_reapplies(self) -> None:
        window = self.open()
        rows = template_rows()
        editor = window.open_editor("Français", "fr", rows=rows)
        self.pump()
        target = tr.game_dir(GAME) / "fr.tsv"
        self.assertTrue(target.is_file())
        self.assertEqual(fmt.read_file(target).translator, "")       # nothing personal pre-filled
        self.assertEqual(window.language_labels(), [tr.ENGLISH, "Français"])
        window.choose(1)
        editor.set_translation(rows[1].row.key, "Bonjour")
        self.assertTrue(editor.save())
        self.assertIn("Bonjour", tr.runtime_path(self.patched).read_text(encoding="utf-8-sig"))
        editor.close()
        # Made again: the existing file is opened, brought up to the template, its lines kept.
        editor = window.open_editor("Français", "fr", rows=rows)
        self.assertEqual(editor.model.row(rows[1].row.key).translation, "Bonjour")
        editor.close()
        window.close()


class UnsavedEditsTests(WindowTests):
    """Codex, #672: closing with edits that could not be saved, answered "No" to "Close anyway?", keeps both
    the editor and the Translations window open."""

    def test_a_failed_save_and_no_keeps_both_windows(self) -> None:
        window = self.open()
        rows = template_rows()
        editor = window.open_editor("Français", "fr", rows=rows)
        self.pump()
        editor.set_translation(rows[1].row.key, "Bonjour")
        self.assertTrue(editor.dirty)
        with mock.patch.object(editor, "save", return_value=False), \
                mock.patch.object(w.messagebox, "askyesno", return_value=False) as ask:
            self.assertFalse(window.close())
        ask.assert_called_once()
        self.assertTrue(editor.top.winfo_exists())
        self.assertTrue(window.top.winfo_exists())
        self.assertTrue(editor.dirty)                                   # the edit is still there
        with mock.patch.object(editor, "save", return_value=False), \
                mock.patch.object(w.messagebox, "askyesno", return_value=True):
            self.assertTrue(window.close())                             # "Yes": both close
        self.assertFalse(window.top.winfo_exists())


def fake_recycle_bin(calls: list):
    """The Recycle Bin call, mocked: records the paths and moves them out of the folder (as Windows would)."""
    def shell(paths):
        calls.append(list(paths))
        for path in paths:
            Path(path).unlink()
    return shell


class ManageFilesTests(WindowTests):
    """The owner, 2026-11-02: "can you add the ability to delete translation files too?" and "and select
    all/ctrl select for multiple selections too?"."""

    def add_three(self, window) -> list[Path]:
        paths = [write_translation(self.temp / f"{code}.txt", language=language, code=code)
                 for language, code in (("Français", "fr"), ("Deutsch", "de"), ("Español", "es"))]
        added = window.add_paths([str(p) for p in paths])
        self.assertEqual(len(added), 3)
        return added

    def test_the_file_list_selects_several_and_select_all_selects_every_row(self) -> None:
        window = self.open()
        self.add_three(window)
        self.assertEqual(window.file_labels(), [tr.ENGLISH, "Deutsch", "Español", "Français"])
        self.assertEqual(str(window.file_list.cget("selectmode")), "extended")   # click, Ctrl+, Shift+click
        window.select(["Deutsch", "Français"])
        self.assertEqual([p.name for p in window.selected_files()], ["de.tsv", "fr.tsv"])
        window.select_all()
        self.assertEqual(window.selected_entries()[0], None)
        self.assertEqual(len(window.selected_files()), 3)
        window.file_list.selection_clear(0, "end")
        for key in ("<Control-a>", "<Control-A>"):                              # Ctrl+A selects all
            self.assertTrue(window.file_list.bind(key))
        self.assertEqual(window.select_all(), "break")
        self.assertEqual(len(window.file_list.curselection()), 4)
        window.close()

    def test_no_is_the_default_and_no_does_nothing(self) -> None:
        window = self.open()
        added = self.add_three(window)
        window.select_all()
        calls: list = []
        asked: list = []

        def ask(parent, title, message):
            asked.append((title, message))
            return False

        self.assertIsNone(window.delete(ask=ask, shell=fake_recycle_bin(calls)))
        self.assertEqual(len(asked), 1)                                         # ONE question
        self.assertEqual(calls, [])
        self.assertTrue(all(p.is_file() for p in added))
        # The default question is the patcher's No-default Yes / No dialog (Return and Escape answer No).
        with mock.patch.object(w.vv_copy_slot_window, "ask_yes_no", return_value=False) as dialog:
            self.assertIsNone(window.delete(shell=fake_recycle_bin(calls)))
        dialog.assert_called_once()
        self.assertEqual(calls, [])
        window.close()

    def test_yes_recycles_every_selected_file_and_skips_english(self) -> None:
        window = self.open()
        added = self.add_three(window)
        window.select([tr.ENGLISH, "Deutsch", "Español"])
        calls: list = []
        asked: list = []

        def ask(parent, title, message):
            asked.append(message)
            return True

        deleted, problems = window.delete(ask=ask, shell=fake_recycle_bin(calls))
        self.assertEqual(problems, [])
        self.assertEqual(len(calls), 1)                                         # one Recycle Bin call
        self.assertEqual(sorted(p.name for p in calls[0]), ["de.tsv", "es.tsv"])
        self.assertEqual(sorted(p.name for p in deleted), sorted(p.name for p in calls[0]))
        message = asked[0]
        self.assertIn("Recycle Bin", message)
        self.assertIn("de.tsv", message)
        self.assertIn("es.tsv", message)
        self.assertIn(w.ENGLISH_KEPT, message)                                  # English named, skipped
        self.assertNotIn("Français", message)
        self.assertEqual(window.file_labels(), [tr.ENGLISH, "Français"])
        self.assertTrue(added[2].is_file() or added[0].is_file())
        window.close()

    def test_english_alone_cannot_be_deleted(self) -> None:
        window = self.open()
        self.add_three(window)
        window.select([tr.ENGLISH])
        asked: list = []
        self.assertIsNone(window.delete(ask=lambda *a: asked.append(a) or True, shell=fake_recycle_bin([])))
        self.assertEqual(asked, [])
        w.messagebox.showinfo.assert_called_with(w.DELETE_TITLE, w.ENGLISH_KEPT, parent=window.top)
        window.close()

    def test_deleting_the_active_language_falls_back_to_english(self) -> None:
        window = self.open()
        self.add_three(window)
        window.choose(window.language_labels().index("Deutsch"))
        runtime = tr.runtime_path(self.patched)
        self.assertTrue(runtime.is_file())
        self.assertEqual(self.app.translation_choices["vv3"]["file"], "installed/de.tsv")
        window.select(["Deutsch"])
        asked: list = []
        deleted, problems = window.delete(ask=lambda p, t, m: asked.append(m) or True, shell=fake_recycle_bin([]))
        self.assertEqual(problems, [])
        self.assertEqual([p.name for p in deleted], ["de.tsv"])
        self.assertIn("goes back to English from its next start", asked[0])
        self.assertFalse(runtime.exists())                                      # removed, as English does
        self.assertEqual(self.app.translation_choices["vv3"]["file"], "")
        self.assertEqual(window.language_box.get(), tr.ENGLISH)
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Food: %d")
        window.close()

    def test_a_missing_recycle_bin_deletes_nothing_and_says_why(self) -> None:
        window = self.open()
        added = self.add_three(window)
        window.choose(window.language_labels().index("Français"))
        window.select(["Français"])

        def no_bin(paths):
            raise tr.RecycleBinUnavailable("the drive Z:\\ has no Recycle Bin")

        deleted, problems = window.delete(ask=lambda *a: True, shell=no_bin)
        self.assertEqual(deleted, [])
        self.assertTrue(all(p.is_file() for p in added))
        self.assertIn("Nothing was deleted", problems[-1])
        self.assertIn("no Recycle Bin", problems[-1])
        self.assertTrue(tr.runtime_path(self.patched).is_file())                # the choice is kept
        self.assertEqual(self.app.translation_choices["vv3"]["file"], "installed/fr.tsv")
        w.messagebox.showerror.assert_called()
        window.close()

    def test_an_editor_open_on_a_deleted_file_is_closed_without_saving(self) -> None:
        window = self.open()
        rows = template_rows()
        editor = window.open_editor("Français", "fr", rows=rows)
        self.pump()
        editor.set_translation(rows[1].row.key, "Bonjour")
        window.select(["Français"])
        window.delete(ask=lambda *a: True, shell=fake_recycle_bin([]))
        self.pump(AUTOSAVE_WAIT)
        self.assertFalse(editor.top.winfo_exists())
        self.assertFalse((tr.game_dir(GAME) / "fr.tsv").exists())   # never saved back
        window.close()

    def test_export_writes_each_selected_file_into_the_chosen_folder(self) -> None:
        window = self.open()
        added = self.add_three(window)
        out = self.temp / "exports"
        out.mkdir()
        window.select_all()                                                     # English skipped
        with mock.patch.object(w.filedialog, "askdirectory", return_value=str(out)) as ask:
            done = window.export()
        ask.assert_called_once()
        self.assertEqual(sorted(p.name for p in done), sorted(p.name for p in added))
        for path in added:
            self.assertEqual((out / path.name).read_bytes(), path.read_bytes())
        # One file: a file name is asked, as before.
        window.select(["Deutsch"])
        target = self.temp / "one.txt"
        with mock.patch.object(w.filedialog, "asksaveasfilename", return_value=str(target)):
            self.assertEqual(window.export(), target)
        self.assertTrue(target.is_file())
        window.close()


class RecycleBinCallTests(TempTranslations):
    """vv_translations._shell_recycle: SHFileOperationW, FO_DELETE with FOF_ALLOWUNDO, through ctypes (Windows
    mocked: no file reaches the real Recycle Bin)."""

    def fake_shell32(self, query_result=0, op_result=0, aborted=False):
        seen = SimpleNamespace(roots=[], ops=[])

        def query(root, info):
            seen.roots.append(root)
            return query_result

        def operation(op):
            obj = op._obj
            seen.ops.append((obj.wFunc, obj.fFlags, obj.pFrom))
            obj.fAnyOperationsAborted = aborted
            return op_result

        return seen, SimpleNamespace(SHQueryRecycleBinW=query, SHFileOperationW=operation)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_the_call_asks_for_the_recycle_bin(self) -> None:
        seen, shell32 = self.fake_shell32()
        file = self.temp / "a.txt"
        file.write_text("x", encoding="utf-8")
        with mock.patch("ctypes.WinDLL", return_value=shell32):
            tr._shell_recycle([file])
        (func, flags, source), = seen.ops
        self.assertEqual(func, 3)                                               # FO_DELETE
        self.assertTrue(flags & 0x40)                                           # FOF_ALLOWUNDO
        self.assertTrue(flags & 0x4000)                                         # FOF_WANTNUKEWARNING
        self.assertEqual(source, str(file.resolve()))
        self.assertTrue(file.is_file())                                         # mocked: nothing moved

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_no_recycle_bin_refuses_before_any_delete(self) -> None:
        seen, shell32 = self.fake_shell32(query_result=-2147024893)
        with mock.patch("ctypes.WinDLL", return_value=shell32):
            with self.assertRaises(tr.RecycleBinUnavailable):
                tr._shell_recycle([self.temp / "a.txt"])
        self.assertEqual(seen.ops, [])

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_an_aborted_operation_is_reported(self) -> None:
        _seen, shell32 = self.fake_shell32(aborted=True)
        with mock.patch("ctypes.WinDLL", return_value=shell32):
            with self.assertRaises(tr.RecycleBinUnavailable):
                tr._shell_recycle([self.temp / "a.txt"])

    def test_only_the_games_own_files_are_deleted(self) -> None:
        installed = tr.install_file(GAME, write_translation(self.temp / "fr.txt"))
        stray = self.temp / "elsewhere.txt"
        stray.write_text("x", encoding="utf-8")
        calls: list = []
        deleted, problems = tr.delete_installed(GAME, [installed, stray], shell=fake_recycle_bin(calls))
        self.assertEqual(deleted, [installed])
        self.assertEqual(calls, [[installed]])
        self.assertTrue(stray.is_file())
        self.assertIn("not an installed translation", problems[0])


AUTOSAVE_WAIT = w.AUTOSAVE_MS / 1000 + 0.3


class RememberedChoiceTests(TempTranslations):
    """Codex, #672: a language chosen before any patched copy existed is used by the copies built later."""

    def setUp(self) -> None:
        super().setUp()
        self.installed = tr.install_file(GAME, write_translation(self.temp / "fr.txt"))
        self.copy = self.temp / "games" / f"{TITLE} - Modded (Stock)"
        (self.copy / tr.PATCHER_FILES).mkdir(parents=True)

    def test_after_build_applies_the_remembered_language(self) -> None:
        app = SimpleNamespace(translation_choices={"vv3": {"file": self.installed.name}})
        self.assertEqual(w.apply_after_build(app, "vv3", self.copy), self.installed)
        self.assertEqual(tr.runtime_path(self.copy).read_bytes(), self.installed.read_bytes())
        app.translation_choices["vv3"]["file"] = ""                    # English chosen: removed
        self.assertIsNone(w.apply_after_build(app, "vv3", self.copy))
        self.assertFalse(tr.runtime_path(self.copy).exists())

    def test_nothing_chosen_leaves_the_copy_as_built(self) -> None:
        tr.apply_choice(self.copy, self.installed)                     # e.g. a file the player put there
        app = SimpleNamespace(translation_choices={})
        self.assertIsNone(w.apply_after_build(app, "vv3", self.copy))
        self.assertTrue(tr.runtime_path(self.copy).is_file())

    def test_apply_patch_applies_the_saved_choice(self) -> None:
        import json
        import vv_fun_patcher as vfp
        settings = self.temp / "patcher_local_settings.json"
        settings.write_text(json.dumps({"translations": {"vv3": {"file": self.installed.name}}}), encoding="utf-8")
        ships = SimpleNamespace(raw={"companion_files": [{"destination": "VVFP Translations.dll"}]})
        other = SimpleNamespace(raw={"companion_files": [{"destination": "VVFP Origins Icons.dll"}]})
        with mock.patch.object(tr, "SETTINGS_FILE", settings):
            vfp._apply_remembered_translation(SimpleNamespace(id="vv3"), self.copy, [other])
            self.assertFalse(tr.runtime_path(self.copy).exists())     # a build without the Translations row
            vfp._apply_remembered_translation(SimpleNamespace(id="vv3"), self.copy, [other, ships])
        self.assertEqual(tr.runtime_path(self.copy).read_bytes(), self.installed.read_bytes())

    def test_apply_patch_calls_it_after_publishing(self) -> None:
        import inspect
        import vv_fun_patcher as vfp
        source = inspect.getsource(vfp.apply_patch)
        self.assertLess(source.index("_apply_remembered_translation(build, output_folder, fun_patches)"),
                        source.index("return output, log_path"))
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        apply_one = gui[gui.index("    def _apply(self)"):gui.index("    def _apply_all(self)")]
        apply_all = gui[gui.index("    def _apply_all(self)"):]
        self.assertIn("vv_translations_window.apply_after_build(self, build.id, output.parent)", apply_one)
        self.assertIn("vv_translations_window.apply_after_build(self, build.id, output.parent)", apply_all)


class EditorTests(TkCase):
    def setUp(self) -> None:
        super().setUp()
        self.rows = template_rows()
        self.path = self.temp / "ed.txt"
        self.tf = tr.new_translation(GAME, "Français", "fr", self.rows)
        self.saved: list = []

    def editor(self) -> w.Editor:
        patch = mock.patch.object(w, "AUTOSAVE_MS", 300)
        patch.start()
        self.addCleanup(patch.stop)
        editor = w.Editor(self.root, GAME, self.path, self.tf, self.rows, on_saved=self.saved.append)
        self.pump()
        return editor

    def test_progress_matches_the_validator(self) -> None:
        editor = self.editor()
        self.assertEqual(editor.model.coverage, 0)
        editor.set_translation(self.rows[0].row.key, "Nourriture : %d")
        editor.set_translation(self.rows[1].row.key, "Bonjour {nom}")           # an error: stays English
        template = tr.template_map(self.rows)
        self.assertAlmostEqual(editor.model.coverage, fmt.validate(editor.model.tf, template, TITLE).coverage)
        self.assertEqual(round(editor.progress["value"]), 33)
        self.assertIn("33% done", editor.progress_var.get())
        self.assertIn("error", editor.tree.item(self.rows[1].row.key, "tags"))
        editor.close()

    def test_untranslated_only_and_search(self) -> None:
        editor = self.editor()
        editor.set_translation(self.rows[0].row.key, "Nourriture : %d")
        editor.untranslated_var.set(True)
        editor.refresh_list()
        self.assertEqual(editor.visible_keys(), [r.row.key for r in self.rows[1:]])
        editor.untranslated_var.set(False)
        editor.search_var.set("baby")
        self.pump()
        self.assertEqual(editor.visible_keys(), [self.rows[2].row.key])
        editor.search_var.set("nourriture")
        self.pump()
        self.assertEqual(editor.visible_keys(), [self.rows[0].row.key])
        editor.close()

    def test_autosave_writes_the_file_a_moment_after_a_change(self) -> None:
        editor = self.editor()
        editor.show(self.rows[2].row.key)
        editor.edit.insert("1.0", "{name} a eu un bébé")
        self.pump(0.02)
        self.assertTrue(editor.dirty)
        self.assertFalse(self.path.exists())
        self.pump(0.8)
        self.assertFalse(editor.dirty)
        self.assertTrue(self.path.is_file())
        self.assertTrue(self.path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(fmt.read_file(self.path).by_key()[self.rows[2].row.key].translation, "{name} a eu un bébé")
        self.assertEqual(self.saved, [self.path])
        editor.close()

    def test_a_missing_placeholder_is_shown_and_placeholders_are_highlighted(self) -> None:
        editor = self.editor()
        key = self.rows[2].row.key
        editor.show(key)
        editor.set_translation(key, "Un bébé est né")
        self.assertIn("{name}", editor.problem_var.get())
        self.assertIn("Stays English", editor.problem_var.get())
        self.assertTrue(editor.english_text.tag_ranges("protected"))
        editor.set_translation(self.rows[2].row.key, "{name} a eu un bébé")
        self.assertTrue(editor.edit.tag_ranges("protected"))
        self.assertEqual(editor.problem_var.get(), "")
        editor.close()

    def test_the_plain_preview_says_what_the_game_font_needs(self) -> None:
        with mock.patch.object(w, "_font_glyphs", return_value=None):
            editor = self.editor()
            key = self.rows[1].row.key
            editor.show(key)
            editor.set_translation(key, "Bonjour à toutes et à tous, chers villageois et villageoises")
            editor.update_preview()
        self.assertIn(w.GAME_FONT_NOTE, editor.note_var.get())
        self.assertIn(w.TOO_WIDE, editor.width_var.get())
        editor.close()


class PreviewTests(unittest.TestCase):
    def test_every_gender_and_every_plural_category_is_shown(self) -> None:
        english = "%s found %d coins"
        rules = fmt.RowRules(subjects={"%1": "person", "%2": "number"})
        person = w.preview_variants(english, "{%1: m=Il|f=Elle|o=Iel} a trouvé %d pièces", "fr", rules)
        self.assertEqual([label for label, _t in person], ["male", "female", "other"])
        self.assertEqual(person[1][1], "Elle a trouvé 3 pièces")     # a number outside a select: a sample 3
        number = w.preview_variants(english, "%s a trouvé %d {%2: one=pièce|other=pièces}", "fr", rules)
        self.assertEqual([label.split()[0] for label, _t in number], fmt.plural_categories("fr"))
        one = next(text for label, text in number if label.startswith("one"))
        self.assertTrue(one.endswith(" pièce"))

    def test_protected_spans_and_missing(self) -> None:
        self.assertEqual(w.protected_spans("Hi {name}, %d%%", ()), [(3, 9), (11, 13)])
        self.assertEqual(w.missing_placeholders("{name}: %d", "Bonjour"), ["%d", "{name}"])
        self.assertEqual(w.missing_placeholders("{name}: %d", ""), [])


class DisplayTextTests(TempTranslations):
    def test_the_patchers_windows_show_the_chosen_language(self) -> None:
        path = write_translation(self.temp / "fr.txt", translations=("Nourriture : %d", "Bonjour {nom}", ""))
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Food: %d")
        tr.set_display_choice(GAME, path)
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Nourriture : %d")
        self.assertEqual(tr.display_text(GAME, "Hello"), "Hello")             # a line with a mistake
        self.assertEqual(tr.display_text(GAME, "{name} had a baby"), "{name} had a baby")
        write_translation(path, translations=("Essen: %d", "", ""))
        os.utime(path, ns=(time.time_ns() + 10 ** 9, time.time_ns() + 10 ** 9))
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Essen: %d")
        tr.set_display_choice(GAME, None)
        self.assertEqual(tr.display_text(GAME, "Food: %d"), "Food: %d")


# ---- drag and drop -------------------------------------------------------------------------------------------

class DropTests(TkCase):
    def test_it_fails_quietly_when_windows_calls_fail(self) -> None:
        import tkinter as tk
        top = tk.Toplevel(self.root)

        def factory_raises():
            raise OSError("no comctl32")

        failing = [
            factory_raises,
            lambda: SimpleNamespace(PROC=lambda f: f, GetAncestor=mock.Mock(return_value=0)),
            lambda: SimpleNamespace(PROC=lambda f: f, GetAncestor=mock.Mock(return_value=1234),
                                    SetWindowSubclass=mock.Mock(return_value=0), DragAcceptFiles=mock.Mock()),
            lambda: SimpleNamespace(PROC=lambda f: f, GetAncestor=mock.Mock(side_effect=OSError("access"))),
            lambda: SimpleNamespace(PROC=mock.Mock(side_effect=TypeError("bad prototype"))),
        ]
        for factory in failing:
            target = w.DropTarget(top, lambda paths: None, api_factory=factory)
            self.assertFalse(target.install())
            self.assertFalse(target.active)
            target.remove()                                    # and closing still works
        top.destroy()

    def test_dropped_files_reach_the_handler_through_the_timer(self) -> None:
        import tkinter as tk
        top = tk.Toplevel(self.root)
        got: list = []
        api = SimpleNamespace(
            PROC=lambda f: f, GetAncestor=mock.Mock(return_value=4321), IsWindow=mock.Mock(return_value=1),
            SetWindowSubclass=mock.Mock(return_value=1), RemoveWindowSubclass=mock.Mock(return_value=1),
            DragAcceptFiles=mock.Mock(), DefSubclassProc=mock.Mock(return_value=0))
        target = w.DropTarget(top, got.extend, api_factory=lambda: api)
        self.assertTrue(target.install())
        api.DragAcceptFiles.assert_called_with(4321, True)
        target.queue.append(r"C:\x\Français.txt")             # as the window procedure leaves them
        self.assertEqual(got, [])                              # never handed over inside the procedure
        self.pump(0.4)
        self.assertEqual(got, [r"C:\x\Français.txt"])
        top.destroy()
        self.pump()
        self.assertFalse(target.active)
        api.RemoveWindowSubclass.assert_called()
        api.DragAcceptFiles.assert_called_with(4321, False)

    @unittest.skipUnless(sys.platform == "win32", "Windows drag and drop")
    def test_a_real_wm_dropfiles_in_a_separate_process(self) -> None:
        """A real subclassed Tk window gets a posted WM_DROPFILES (also after Tk rebuilds its frame) and closes
        cleanly; run in its own process so a failure can never take the test run down."""
        script = textwrap.dedent(r'''
            import ctypes, struct, sys, tkinter as tk
            sys.path.insert(0, sys.argv[1])
            import vv_translations_window as w
            k32 = ctypes.WinDLL("kernel32")
            k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]; k32.GlobalAlloc.restype = ctypes.c_void_p
            k32.GlobalLock.argtypes = [ctypes.c_void_p]; k32.GlobalLock.restype = ctypes.c_void_p
            k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            u32 = ctypes.WinDLL("user32")
            u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
            def hdrop(paths):
                data = struct.pack("<IiiII", 20, 0, 0, 0, 1) + ("\0".join(paths) + "\0\0").encode("utf-16-le")
                h = k32.GlobalAlloc(2, len(data)); p = k32.GlobalLock(h)
                ctypes.memmove(p, data, len(data)); k32.GlobalUnlock(h); return h
            root = tk.Tk(); top = tk.Toplevel(root); top.transient(root)
            got = []
            t = w.DropTarget(top, got.extend); root.update()
            if not t.install(): print("NOHOOK"); sys.exit(0)
            u32.PostMessageW(t.hwnd, w.WM_DROPFILES, hdrop(["C:\\a\\Fran\u00e7ais.txt", "C:\\b.txt"]), 0)
            root.after(500, lambda: (top.wm_transient(""), top.update_idletasks()))
            root.after(1000, lambda: u32.PostMessageW(t.hwnd, w.WM_DROPFILES, hdrop(["C:\\c.txt"]), 0))
            root.after(1600, top.destroy); root.after(1900, root.destroy)
            root.mainloop()
            print("GOT", ascii(got), t.active)
        ''')
        try:
            result = subprocess.run([sys.executable, "-I", "-c", script, str(ROOT / "src")], capture_output=True,
                                    text=True, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            self.fail("the drag-and-drop window hung")
        if "NOHOOK" in result.stdout:
            self.skipTest("this Windows has no window subclassing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(r"GOT ['C:\\a\\Fran\xe7ais.txt', 'C:\\b.txt', 'C:\\c.txt'] False", result.stdout)


if __name__ == "__main__":
    unittest.main()
