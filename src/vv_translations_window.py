"""The Translations window (Tools tab): the language each game uses, the built-in editor, Add / Export and
Share on GitHub.

The owner (2026-11-01): one window per patcher, "Translations...", with
  * a Language list per game ("English (original)" and every installed translation by its own name, "by
    <credit>" when credited).  The choice is remembered per game in the patcher's settings (key
    "translations") and the patched game uses it from its next start, with no re-patching: the file is copied
    to "<patched game>\\Virtual Villagers Fun Patcher Files\\Translation\\Translation.txt"
    (vv_translations.apply_choice), English removes it;
  * Make a translation: a language from the list (or Other...), the template read from the player's own game,
    and the built-in editor (two columns, search, untranslated only, % done, each line's problems, protected
    placeholders, a preview in the game's own letters with every gender and plural form, autosave);
  * the Files list, several selectable (the owner, 2026-11-02: "select all/ctrl select for multiple
    selections": click, Ctrl+click, Shift+click, Ctrl+A, Select All);
  * Add translation file... (and a file dropped on the window: Windows' own WM_DROPFILES, no extra packages),
    Export... (one file, or each selected file into a folder), Delete... (the owner, 2026-11-02: "can you add
    the ability to delete translation files too?": one Yes / No question, No the default, the files to the
    Recycle Bin, never a hard delete; English (original) skipped; a deleted active language falls back to
    English), and Share on GitHub... (the owner's question first, No the default; a typed credit
    name, never pre-filled, never an email address; then the file is exported, shown in Explorer, and the
    new-issue page opens with nothing personal in its address).

Email addresses are never saved and are rejected from translation files: nothing here stores one, and the
credit name is written only into the translation file itself, never into the settings.
"""
from __future__ import annotations

import ctypes
import glob
import os
import re
import struct
import subprocess
import sys
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import vv_copy_slot_window
import vv_translation_format as fmt
import vv_translations as tr
import vv_translations_github

TITLE = "Translations"
SETTINGS_KEY = "translations"           # the patcher's local settings: {"vv3": {"file": ..., "folders": [...]}}
OTHER_LANGUAGE = "Other..."
SHARE_TITLE = "Share on GitHub"
SHARE_PROMPT = (
    "This button allows you to share your game translation to the patcher's Public Github. IF ACCEPTED, "
    "everyone who uses this patcher will be able to see your translation in the game and your username will "
    "be included in the credits. Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!\n\n"
    "Email addresses are never saved and are rejected from translation files.\n\n"
    "This feature is meant to be a community collaboration tool for game modding only.\n\n"
    "You will need a Github account to proceed. Continue?"
)
SHARE_SENTENCE = "If you want to share your translation, consider going to the Patcher's GitHub page and adding it!"
SHARE_HOW = "How: press Share on GitHub..., drag the file in, press Submit."
CREDIT_TITLE = "Credit name"
CREDIT_HINT = ("Type the name you want to be credited as (a nickname is fine). It is shown publicly with your "
               "translation. " + fmt.EMAIL_SENTENCE)
# A separate note beside the owner's exact Share question (never part of it): the owner, 2026-11-02, "PLEASE RUN
# EVERY SINGLE USER-SUBMITTED FILE THROUGH VIRUSTOTAL AND REJECT ANYTHING THAT IS FLAGGED".
VIRUSTOTAL_NOTE = ("Every shared file is sent to VirusTotal to be scanned before anyone looks at it, and anything "
                   "it flags is refused. That is one more reason never to put private details in a translation.")
ISSUE_URL ="https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/new"
PATCH_ROW_NOTE = ("The game must be patched with the \"Translations\" row (it is on by default); the language "
                  "is used from the game's next start, with no re-patching.")
GAME_FONT_NOTE = "game-font preview needs Render Unicode with In-Game Fonts"
TOO_WIDE = "may not fit its box"
AUTOSAVE_MS = 1500
WIDE_RATIO = 1.25           # wider than the English by this much (and WIDE_MARGIN pixels) warns
WIDE_MARGIN = 12
SAMPLE_NAME = "Kai"
CREDIT_MAX = 80
FONT_CHOICES = (("Story, menu and button letters", "ldwBurweed27"), ("Small letters (Details, Tech, logs)",
                                                                       "ldwarialbold"))
TK_FONTS = {"ldwBurweed27": ("Comic Sans MS", 14, "bold"), "ldwarialbold": ("Arial", 10, "bold")}
PREVIEW_BG = "#3b2a1a"


# ---- the settings ------------------------------------------------------------------------------------------

def _store(app) -> dict:
    store = getattr(app, "translation_choices", None)
    if not isinstance(store, dict):
        store = {}
        try:
            app.translation_choices = store
        except (AttributeError, TypeError):
            pass
    return store


def _entry(app, number: int) -> dict:
    store = _store(app)
    entry = store.get(f"vv{number}")
    if not isinstance(entry, dict):
        entry = {}
        store[f"vv{number}"] = entry
    return entry


def _save_settings(app) -> None:
    save = getattr(app, "_save_settings", None)
    if callable(save):
        try:
            save()
        except OSError:
            pass


def chosen_name(app, number: int) -> str:
    """The file name of the translation chosen for game `number`, "" for English (the default)."""
    value = _entry(app, number).get("file", "")
    return value if isinstance(value, str) else ""


def chosen_path(app, number: int) -> Path | None:
    name = chosen_name(app, number)
    if not name or Path(name).name != name:
        return None
    return tr.find_installed(number, name)


def remember_choice(app, number: int, path: Path | None) -> None:
    _entry(app, number)["file"] = Path(path).name if path else ""
    tr.set_display_choice(number, path)
    _save_settings(app)


def remember_folder(app, number: int, folder: Path) -> None:
    entry = _entry(app, number)
    folders = [f for f in entry.get("folders", []) if isinstance(f, str)]
    if str(folder) not in folders:
        folders.append(str(folder))
    entry["folders"] = folders
    _save_settings(app)


def apply_after_build(app, game, folder: Path) -> Path | None:
    """After a successful build (the GUI's _apply / _apply_all; apply_patch does the same from the saved
    settings): the new patched copy gets the language remembered for its game, so a language chosen before
    any patched copy existed is used (Codex, #672).  Nothing chosen: the copy is left as built.  Never
    raises: a copy it cannot write keeps English, and the Translations window applies the choice again."""
    try:
        return tr.apply_remembered(game, Path(folder), settings={SETTINGS_KEY: _store(app)})
    except (OSError, ValueError):
        return None


def restore_display_choices(app) -> None:
    """At start: the patcher's own windows use each game's remembered language (vv_translations.display_text)."""
    for number in tr.TITLES:
        try:
            tr.set_display_choice(number, chosen_path(app, number))
        except OSError:
            pass


# ---- the player's game folders -------------------------------------------------------------------------------

def _var(value) -> str:
    try:
        text = value.get() if hasattr(value, "get") else value
    except (tk.TclError, RuntimeError):
        return ""
    return text.strip() if isinstance(text, str) else ""


def source_folders(app, number: int) -> list[Path]:
    """The game folders the patcher knows for game `number`: the All 5 Games tab's folder and the One Game
    tab's executable when it is this game."""
    title = tr.TITLES[number]
    out = []
    value = _var(getattr(app, "all_folder_vars", {}).get(f"vv{number}", ""))
    if value:
        path = Path(value)
        out.append(path.parent if path.suffix.lower() == ".exe" else path)
    exe = _var(getattr(app, "exe_var", ""))
    if exe and Path(exe).stem.casefold().startswith(title.casefold()):
        out.append(Path(exe).parent)
    return out


def _output_root(app) -> Path | None:
    get = getattr(app, "_output_root", None)
    if callable(get):
        try:
            root = get()
        except (OSError, tk.TclError):
            return None
        return Path(root) if root else None
    return None


def _unique(paths) -> list[Path]:
    out, seen = [], set()
    for path in paths:
        try:
            key = os.path.normcase(str(Path(path).resolve()))
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            out.append(Path(path))
    return out


def patched_folders(app, number: int) -> list[Path]:
    """Every patched copy of game `number` the patcher knows: the folder it last built, "<title> - Modded..."
    folders in the chosen output folder and beside the original game, a chosen folder that is itself a patched
    copy, and the folders the player pointed to before.  Only folders with a "Virtual Villagers Fun Patcher
    Files" folder count."""
    title = tr.TITLES[number]
    candidates: list[Path] = []
    last = (getattr(app, "last_modified_paths", None) or {}).get(f"vv{number}")
    if last:
        last = Path(last)
        candidates.append(last.parent if last.suffix.lower() == ".exe" else last)
    roots = [_output_root(app)]
    for source in source_folders(app, number):
        candidates.append(source)
        roots.append(source.parent)
    for root in _unique(r for r in roots if r):
        try:
            candidates.extend(sorted(Path(p) for p in glob.glob(str(root / (glob.escape(title) + " - Modded*")))))
        except OSError:
            continue
    candidates.extend(Path(f) for f in _entry(app, number).get("folders", []) if isinstance(f, str))
    return [p for p in _unique(candidates) if (p / tr.PATCHER_FILES).is_dir()]


def find_exe(folder: Path, number: int) -> Path | None:
    """The game executable in `folder`: "<title> - Modded.exe" first, any other patched build, the game's own."""
    title = tr.TITLES[number]
    folder = Path(folder)
    exact = tr.find_game_exe(folder, number)
    if exact is not None:
        return exact
    for path in sorted(glob.glob(str(folder / (glob.escape(title) + " - Modded*.exe")))):
        if Path(path).is_file():
            return Path(path)
    return None


def template_folders(app, number: int) -> list[Path]:
    """Folders the English template can be read from: the patched copies first (their text is what the game
    shows), then the original game."""
    return [f for f in _unique(patched_folders(app, number) + source_folders(app, number))
            if find_exe(f, number) is not None]


def apply_to_games(number: int, translation: Path | None, folders: list[Path]) -> tuple[list[Path], list[str]]:
    """The choice copied into every patched copy (English: removed).  (done, problems)."""
    done, problems = [], []
    for folder in folders:
        try:
            tr.apply_choice(folder, translation)
            done.append(folder)
        except OSError as exc:
            problems.append(f"{folder}: {exc}")
    return done, problems


# ---- checking, adding, exporting ----------------------------------------------------------------------------

@dataclass
class Checked:
    tf: fmt.TranslationFile | None
    report: fmt.Report | None
    refused: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.tf is not None and not self.refused


def check_translation(path: Path, number: int, template: dict | None = None) -> Checked:
    """A file checked for game `number`: refused (unreadable, another game, an email address, no language or
    code) or its report (coverage, the lines that stay English)."""
    try:
        tf = fmt.read_file(Path(path))
    except (OSError, fmt.FormatError) as exc:
        return Checked(None, None, [str(exc)])
    report = fmt.validate(tf, template, tr.TITLES[number])
    refused = list(report.file_errors)
    for row in tf.rows:                     # an email address anywhere refuses the whole file
        if fmt.find_emails(row.translation):
            refused.append(f"line {row.line} contains an email address. {fmt.EMAIL_SENTENCE}")
    return Checked(tf, report, list(dict.fromkeys(refused)))


def report_text(checked: Checked, limit: int = 30) -> str:
    if checked.tf is None or checked.report is None:
        return "This file cannot be used:\n\n" + "\n".join(checked.refused)
    report = checked.report
    lines = []
    if checked.refused:
        lines.append("This file cannot be used:")
        lines.extend(f"  {problem}" for problem in checked.refused)
        lines.append("")
    lines.append(f"{checked.tf.language or '?'} ({checked.tf.code or '?'}): {report.summary()}")
    if report.errors:
        lines.append("")
        lines.append("These lines have mistakes and stay English:")
        lines.extend(f"  {issue}" for issue in report.errors[:limit])
        if len(report.errors) > limit:
            lines.append(f"  ...and {len(report.errors) - limit} more")
    return "\n".join(lines)


def add_translation(number: int, path: Path, template: dict | None = None) -> tuple[Path | None, Checked]:
    """Add translation file...: checked, then copied into the translations folder (None when refused)."""
    checked = check_translation(path, number, template)
    if not checked.ok:
        return None, checked
    return tr.install_file(number, Path(path)), checked


def export_name(number: int, language: str) -> str:
    return fmt.file_name(tr.TITLES[number], language)


def export_translation(source: Path, destination: Path) -> Path:
    tr.export_copy(Path(source), Path(destination))
    return Path(destination)


DELETE_TITLE = "Delete translations"
ENGLISH_KEPT = f"{tr.ENGLISH} is the game's own text: it can't be deleted and is skipped."


def delete_question(number: int, paths: list[Path], english: bool, active: str) -> str:
    """The one Yes / No question Delete... asks: every file named, English (original) named when it was
    selected, and the game's active language named when it is one of them."""
    short = tr.TITLES[number].removeprefix("Virtual Villagers - ")
    what = "this translation file" if len(paths) == 1 else "these %d translation files" % len(paths)
    goes = "It goes" if len(paths) == 1 else "They go"
    lines = [f"Delete {what} of {short}? {goes} to the Recycle Bin.", ""]
    lines += [f"    {Path(p).name}" for p in paths]
    if english:
        lines += ["", ENGLISH_KEPT]
    if active:
        lines += ["", f"{active} is the language {short} uses now: the game goes back to English from its next "
                      "start."]
    return "\n".join(lines)


def delete_translations(app, number: int, paths, *, ask=None, shell=None, parent=None):
    """Delete...: every selected translation file of game `number` to the Recycle Bin after one Yes / No question
    (No the default; No does nothing).  `paths` may hold None for English (original), which is skipped and
    named.  A deleted file that is the game's chosen language: the choice falls back to English from the game's
    next start, and the copied Translation.txt is removed from every patched copy, as choosing English does.
    (deleted, problems) -- None when nothing was asked or the answer was No."""
    english = any(p is None for p in paths)
    files = list(dict.fromkeys(Path(p) for p in paths if p is not None))
    if not files:
        return None
    active_name = chosen_name(app, number)
    active = next((p.name for p in files if p.name == active_name), "")
    ask = ask or vv_copy_slot_window.ask_yes_no
    if not ask(parent, DELETE_TITLE, delete_question(number, files, english, active)):
        return None
    deleted, problems = tr.delete_installed(number, files, shell=shell)
    if active and any(p.name == active for p in deleted):
        remember_choice(app, number, None)
        _done, failed = apply_to_games(number, None, patched_folders(app, number))
        problems += failed
    return deleted, problems


def export_dir() -> Path:
    """Where Share on GitHub... offers to put the file: beside the patcher's translations folder."""
    return tr.TRANSLATIONS_DIR.parent / "Translation exports"


# ---- sharing ---------------------------------------------------------------------------------------------------

def credit_problem(name: str) -> str | None:
    """Why `name` cannot be the credit (None: it can)."""
    name = (name or "").strip()
    if not name:
        return "Type the name you want to be credited as. It cannot be left empty."
    if fmt.find_emails(name) or "@" in name:
        return "That looks like an email address. " + fmt.EMAIL_SENTENCE + " Type a name instead."
    if len(name) > CREDIT_MAX:
        return f"The name can be at most {CREDIT_MAX} characters long."
    if any(ch in name for ch in "\t\r\n"):
        return "The name must be on one line."
    return None


def share_url(game_title: str, language: str, code: str, coverage: float | None = None) -> str:
    """The new-issue page with the form filled in: game, language and code (and the coverage); never the
    credit name or anything else personal."""
    params = [
        ("template", "translation.yml"),
        ("title", f"Translation: {game_title} - {language}"),
        ("game", game_title),
        ("language", language),
        ("code", code),
    ]
    if coverage is not None:
        params.append(("coverage", f"{coverage:.0f}%"))
    return ISSUE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def reveal_in_explorer(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{Path(path)}"')


def build_credit(parent):
    """The credit name box: empty, typed by hand.  (window, entry, answer) -- answer["name"] is None until OK
    accepts a name."""
    top = tk.Toplevel(parent)
    top.title(CREDIT_TITLE)
    if parent is not None:
        top.transient(parent)
    answer = {"name": None}
    frame = ttk.Frame(top, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=CREDIT_HINT, wraplength=460, justify="left").pack(anchor="w")
    ttk.Label(frame, text=VIRUSTOTAL_NOTE, wraplength=460, justify="left", foreground="#555555").pack(
        anchor="w", pady=(6, 0))
    name_var = tk.StringVar(master=top, value="")
    entry = ttk.Entry(frame, textvariable=name_var, width=40)
    entry.pack(anchor="w", pady=(10, 0), fill="x")
    problem_var = tk.StringVar(master=top, value="")
    ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=460, justify="left").pack(
        anchor="w", pady=(4, 0))
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e", pady=(12, 0))

    def ok(_event=None) -> None:
        problem = credit_problem(name_var.get())
        if problem:
            problem_var.set(problem)
            return
        answer["name"] = name_var.get().strip()
        top.destroy()

    def cancel(_event=None) -> None:
        answer["name"] = None
        top.destroy()

    ok_button = ttk.Button(buttons, text="OK", command=ok)
    ok_button.pack(side="left")
    ttk.Button(buttons, text="Cancel", command=cancel).pack(side="left", padx=(8, 0))
    entry.bind("<Return>", ok)
    top.bind("<Escape>", cancel)
    top.protocol("WM_DELETE_WINDOW", cancel)
    top.entry, top.ok_button, top.problem_var, top.name_var = entry, ok_button, problem_var, name_var
    entry.focus_set()
    try:
        top.grab_set()
    except tk.TclError:
        pass
    return top, entry, answer


def ask_credit_name(parent) -> str | None:
    top, _entry_widget, answer = build_credit(parent)
    top.wait_window()
    return answer["name"]


def _choose_export_folder(parent) -> Path | None:
    folder = export_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path.home()
    chosen = filedialog.askdirectory(parent=parent, title="Choose where to save the file to share",
                                     initialdir=str(folder), mustexist=True)
    return Path(chosen) if chosen else None


def share_on_github(parent, number: int, path: Path, *, ask=None, ask_credit=None, choose_folder=None,
                    reveal=None, browse=None, template: dict | None = None) -> Path | None:
    """Share on GitHub...: the owner's question first (No the default; No does nothing at all), then the
    credit name typed by hand, written into the file's @translator row; the file exported, shown in Explorer,
    and the new-issue page opened.  The exported file, or None when nothing was done."""
    ask = ask or vv_copy_slot_window.ask_yes_no
    if not ask(parent, SHARE_TITLE, SHARE_PROMPT):
        return None
    name = (ask_credit or ask_credit_name)(parent)
    if name is None:
        return None
    problem = credit_problem(name)
    if problem:
        messagebox.showerror(CREDIT_TITLE, problem, parent=parent)
        return None
    title = tr.TITLES[number]
    try:
        tf = fmt.read_file(Path(path))
    except (OSError, fmt.FormatError) as exc:
        messagebox.showerror(SHARE_TITLE, f"The file cannot be read: {exc}", parent=parent)
        return None
    tf.set_info("@translator", "", name.strip())
    problems = fmt.check_info(tf, title)
    report = fmt.validate(tf, template, title)
    problems += report.file_errors
    problems += [f"line {row.line} contains an email address. {fmt.EMAIL_SENTENCE}"
                 for row in tf.rows if fmt.find_emails(row.translation)]
    problems = list(dict.fromkeys(problems))
    if problems:
        messagebox.showerror(SHARE_TITLE, "This file cannot be shared:\n\n" + "\n".join(problems), parent=parent)
        return None
    folder = (choose_folder or _choose_export_folder)(parent)
    if not folder:
        return None
    try:
        fmt.write_file(Path(path), tf)
        target = export_translation(Path(path), Path(folder) / export_name(number, tf.language))
    except OSError as exc:
        messagebox.showerror(SHARE_TITLE, f"The file could not be saved: {exc}", parent=parent)
        return None
    (reveal or reveal_in_explorer)(target)
    (browse or webbrowser.open)(share_url(title, tf.language, tf.code, report.coverage))
    return target


# ---- drag and drop (Windows' own WM_DROPFILES; no extra packages) -------------------------------------------

WM_DROPFILES = 0x0233
WM_NCDESTROY = 0x0082
GA_ROOT = 2
_SUBCLASS_ID = 0x56565450
_KEEP_ALIVE: list = []      # every window procedure handed to Windows stays alive for the whole run
_API = None


def _win_api():
    """The Windows calls drag-and-drop needs, with full 64-bit argument types (a pointer cut to 32 bits is
    the classic way a ctypes window procedure crashes)."""
    global _API
    if _API is not None:
        return _API
    if sys.platform != "win32":
        raise OSError("drag and drop needs Windows")
    user32 = ctypes.WinDLL("user32")
    shell32 = ctypes.WinDLL("shell32")
    comctl32 = ctypes.WinDLL("comctl32")
    vp, uint, wparam, lparam = ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
    proc_type = ctypes.WINFUNCTYPE(lparam, vp, uint, wparam, lparam, ctypes.c_size_t, ctypes.c_size_t)

    def fn(dll, name, args, res):
        f = getattr(dll, name)
        f.argtypes, f.restype = args, res
        return f

    _API = SimpleNamespace(
        PROC=proc_type,
        GetAncestor=fn(user32, "GetAncestor", [vp, uint], vp),
        IsWindow=fn(user32, "IsWindow", [vp], ctypes.c_int),
        DragAcceptFiles=fn(shell32, "DragAcceptFiles", [vp, ctypes.c_int], None),
        DragQueryFileW=fn(shell32, "DragQueryFileW", [vp, uint, ctypes.c_wchar_p, uint], uint),
        DragFinish=fn(shell32, "DragFinish", [vp], None),
        SetWindowSubclass=fn(comctl32, "SetWindowSubclass", [vp, proc_type, ctypes.c_size_t, ctypes.c_size_t],
                             ctypes.c_int),
        RemoveWindowSubclass=fn(comctl32, "RemoveWindowSubclass", [vp, proc_type, ctypes.c_size_t], ctypes.c_int),
        DefSubclassProc=fn(comctl32, "DefSubclassProc", [vp, uint, wparam, lparam], lparam),
    )
    return _API


class DropTarget:
    """Files dropped on `window` handed to `on_files(paths)`.

    The window procedure only reads the dropped paths (DragQueryFileW, DragFinish) into a list: it never calls
    Tk, whose lock Tk itself holds while Windows delivers the message.  A Tk timer hands the list to
    `on_files`.  The subclass is put back when Tk rebuilds the window's frame and removed when the window
    closes; when anything fails, the window simply has no drag and drop (the Add button still works)."""

    POLL_MS = 250

    def __init__(self, window, on_files, api_factory=None):
        self.window = window
        self.on_files = on_files
        self.api_factory = api_factory or _win_api
        self.api = None
        self.proc = None
        self.hwnd = None
        self.queue: list[str] = []
        self.after_id = None
        self.active = False

    def install(self) -> bool:
        try:
            self.api = self.api_factory()
            api = self.api

            def procedure(hwnd, msg, wparam, lparam, uid, _ref):
                try:
                    if msg == WM_DROPFILES:
                        self._read_drop(wparam)
                        return 0
                    if msg == WM_NCDESTROY:
                        api.RemoveWindowSubclass(hwnd, self.proc, _SUBCLASS_ID)
                        if self.hwnd == hwnd:
                            self.hwnd = None
                except Exception:  # noqa: BLE001 -- nothing may escape into Windows
                    pass
                return api.DefSubclassProc(hwnd, msg, wparam, lparam)

            self.proc = api.PROC(procedure)
            _KEEP_ALIVE.append(self.proc)
            if not self._hook():
                return False
        except Exception:  # noqa: BLE001 -- no drag and drop: the Add button is enough
            self.active = False
            return False
        self.active = True
        try:
            self.window.bind("<Destroy>", self._destroyed, add="+")
            self.after_id = self.window.after(self.POLL_MS, self._poll)
        except tk.TclError:
            pass
        return True

    def _frame(self):
        self.window.update_idletasks()
        return self.api.GetAncestor(self.window.winfo_id(), GA_ROOT)

    def _hook(self) -> bool:
        hwnd = self._frame()
        if not hwnd:
            return False
        if not self.api.SetWindowSubclass(hwnd, self.proc, _SUBCLASS_ID, 0):
            return False
        self.api.DragAcceptFiles(hwnd, True)
        self.hwnd = hwnd
        return True

    def _read_drop(self, hdrop) -> None:
        api = self.api
        try:
            count = api.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
            for index in range(min(count, 64)):
                length = api.DragQueryFileW(hdrop, index, None, 0)
                buffer = ctypes.create_unicode_buffer(length + 1)
                api.DragQueryFileW(hdrop, index, buffer, length + 1)
                self.queue.append(buffer.value)
        finally:
            api.DragFinish(hdrop)

    def _poll(self) -> None:
        if not self.active:
            return
        try:
            self.after_id = self.window.after(self.POLL_MS, self._poll)
        except tk.TclError:
            return
        try:
            hwnd = self._frame()
            if hwnd and hwnd != self.hwnd:
                self._hook()                    # Tk rebuilt the window's frame
        except Exception:  # noqa: BLE001
            pass
        if self.queue:
            paths, self.queue = self.queue, []
            self.on_files(paths)

    def _destroyed(self, event) -> None:
        if event.widget is self.window:
            self.remove()

    def remove(self) -> None:
        self.active = False
        try:
            if self.after_id is not None:
                self.window.after_cancel(self.after_id)
        except tk.TclError:
            pass
        self.after_id = None
        hwnd, self.hwnd = self.hwnd, None
        if hwnd and self.api is not None:
            try:
                if self.api.IsWindow(hwnd):
                    self.api.DragAcceptFiles(hwnd, False)
                    self.api.RemoveWindowSubclass(hwnd, self.proc, _SUBCLASS_ID)
            except Exception:  # noqa: BLE001
                pass


# ---- the editor ------------------------------------------------------------------------------------------------

_TOKEN_RE = re.compile(fmt._PRINTF_RE.pattern + r"|\{[A-Za-z_][A-Za-z0-9_]*\}")


def protected_spans(text: str, tokens=()) -> list[tuple[int, int]]:
    """Where the placeholders (%d, %s, {name}) and the game's own tokens are in `text`."""
    spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text) if m.group(0) != "%%"]
    for token in tokens:
        if not token:
            continue
        start = text.find(token)
        while start >= 0:
            spans.append((start, start + len(token)))
            start = text.find(token, start + len(token))
    return sorted(set(spans))


def missing_placeholders(english: str, translation: str, tokens=()) -> list[str]:
    """The English's placeholders and tokens the translation lacks (shown in the edit box's warning)."""
    if not translation:
        return []
    out = []
    for conv in fmt.printf_conversions(english):
        if fmt.printf_conversions(translation).count(conv) < fmt.printf_conversions(english).count(conv):
            if conv not in out:
                out.append(conv)
    for name in fmt.named_variables(english):
        token = "{" + name + "}"
        if name not in fmt.named_variables(translation) and token not in out:
            out.append(token)
    for token in tokens:
        if token and token in english and token not in translation and token not in out:
            out.append(token)
    return out


def _fill(text: str, values: dict, subjects: dict) -> str:
    """The sample values in place of the placeholders, as the game would fill them."""
    index = 0

    def printf(m):
        nonlocal index
        conv = m.group(0)
        if conv == "%%":
            return "%"
        index += 1
        value = values.get(f"%{index}")
        if conv[-1] == "s":
            return SAMPLE_NAME if subjects.get(f"%{index}") != "number" or value is None else str(value)
        if conv[-1] in "eEfgG":
            return "2.5"
        if conv[-1] == "c":
            return "x"
        return str(value if isinstance(value, int) else 3)

    text = fmt._PRINTF_RE.sub(printf, text)

    def var(m):
        name = m.group(1)
        if subjects.get(name) == "number":
            value = values.get(name)
            return str(value if isinstance(value, int) else 3)
        return SAMPLE_NAME

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", var, text)


def preview_variants(english: str, translation: str, code: str, rules: fmt.RowRules | None = None
                     ) -> list[tuple[str, str]]:
    """The line as the game shows it, once per gender (male, female, other) and once per plural category of
    the language (with an example number), with sample values in the placeholders.  [(label, text)]."""
    text = translation or english
    code = code or "en"
    subjects = dict(fmt.infer_subjects(english))
    if rules is not None:
        subjects.update(rules.subjects)
    try:
        selects = fmt.parse_selects(text)
    except fmt.SelectError:
        return [("", _fill(text, {}, subjects))]
    kinds: dict[str, str] = {}
    for sel in selects:
        kinds.setdefault(sel.subject, subjects.get(sel.subject) or sel.kind)
    people = [s for s, k in kinds.items() if k == "person"]
    numbers = [s for s, k in kinds.items() if k == "number"]
    base: dict = {s: "o" for s in people}
    base.update({s: fmt.plural_example(code, "other") for s in numbers})
    variants = []
    try:
        if people:
            for sex, label in (("m", "male"), ("f", "female"), ("o", "other")):
                values = dict(base, **{s: sex for s in people})
                variants.append((label, _fill(fmt.render(text, values, code), values, subjects)))
        if numbers:
            for category in fmt.plural_categories(code):
                n = fmt.plural_example(code, category)
                values = dict(base, **{s: n for s in numbers})
                variants.append((f"{category} ({n})", _fill(fmt.render(text, values, code), values, subjects)))
        if not variants:
            variants.append(("", _fill(fmt.render(text, {}, code), {}, subjects)))
    except fmt.SelectError:
        return [("", _fill(text, {}, subjects))]
    return variants


def _font_glyphs():
    """The shared glyph module of "Render Unicode with In-Game Fonts", when this build has it."""
    try:
        import vv_font_glyphs
    except ImportError:
        return None
    return vv_font_glyphs


class EditorModel:
    """The rows being translated, their problems and the progress -- everything the editor shows that is
    not drawing."""

    def __init__(self, tf: fmt.TranslationFile, rows: list[tr.TemplateRow], changed=()):
        self.tf = tf
        self.rules = {r.row.key: r.rules for r in rows}
        self.context = {r.row.key: r.context for r in rows}
        self.template = tr.template_map(rows)
        self.changed = set(changed)
        self.by_key = {row.key: row for row in tf.rows}
        self.order = [row.key for row in tf.rows]
        self._issues: dict[str, list[fmt.Issue]] = {}

    def row(self, key: str) -> fmt.Row:
        return self.by_key[key]

    def issues(self, key: str) -> list[fmt.Issue]:
        if key not in self._issues:
            row = self.by_key[key]
            english, rules = self.template.get(key, (row.english, None))
            self._issues[key] = fmt.check_row(english, row.translation, rules, row.line, key)
        return self._issues[key]

    def has_error(self, key: str) -> bool:
        return any(i.severity == "error" for i in self.issues(key))

    def set(self, key: str, text: str) -> bool:
        row = self.by_key[key]
        if row.translation == text:
            return False
        row.translation = text
        self._issues.pop(key, None)
        self.changed.discard(key)
        return True

    @property
    def total(self) -> int:
        return len(self.template) if self.template else len(self.order)

    @property
    def used(self) -> int:
        return sum(1 for key in self.order if key in self.template and self.by_key[key].translation
                   and not self.has_error(key))

    @property
    def coverage(self) -> float:
        return 100.0 * self.used / self.total if self.total else 0.0

    def visible(self, search: str = "", untranslated_only: bool = False) -> list[str]:
        needle = search.casefold().strip()
        out = []
        for key in self.order:
            row = self.by_key[key]
            if untranslated_only and row.translation:
                continue
            if needle and needle not in row.english.casefold() and needle not in row.translation.casefold() \
                    and needle not in key.casefold():
                continue
            out.append(key)
        return out


def _one_line(text: str) -> str:
    return text.replace("\r", "").replace("\n", " ⏎ ")


class Editor:
    """The built-in editor: English on the left, the translation on the right; the selected line below, with
    its problems and its preview in the game's letters.  Saves by itself a moment after each change."""

    def __init__(self, parent, number: int, path: Path, tf: fmt.TranslationFile, rows: list[tr.TemplateRow],
                 *, images_dir: Path | None = None, on_saved=None, changed=()):
        self.number, self.path = number, Path(path)
        self.model = EditorModel(tf, rows, changed)
        self.images_dir = Path(images_dir) if images_dir else None
        self.on_saved = on_saved
        self.dirty = False
        self.save_after = None
        self.preview_after = None
        self.current: str | None = None
        self.loading = False
        self.photos: list = []
        self.fonts: dict = {}
        top = self.top = tk.Toplevel(parent)
        top.title(f"Translation editor - {tr.TITLES[number]} - {tf.language}")
        if parent is not None:
            top.transient(parent)
        width = min(1180, top.winfo_screenwidth() - 60)
        height = min(840, top.winfo_screenheight() - 120)
        top.geometry(f"{width}x{height}")
        top.minsize(min(700, width), min(480, height))
        self._build(width)
        self.refresh_list()
        self.update_progress()
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Control-s>", lambda _e: self.save())
        top.bind("<Destroy>", self._gone, add="+")
        top.editor = self
        visible = self.model.visible()
        if visible:
            self.tree.selection_set(visible[0])
            self.tree.focus(visible[0])
            self.show(visible[0])

    # -- layout
    def _build(self, width: int) -> None:
        top = self.top
        bar = ttk.Frame(top, padding=(10, 8, 10, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar(master=top)
        search = ttk.Entry(bar, textvariable=self.search_var, width=28)
        search.pack(side="left", padx=(4, 12))
        self.untranslated_var = tk.BooleanVar(master=top, value=False)
        ttk.Checkbutton(bar, text="Show untranslated only", variable=self.untranslated_var,
                        command=self.refresh_list).pack(side="left")
        self.progress_var = tk.StringVar(master=top)
        ttk.Label(bar, textvariable=self.progress_var).pack(side="right")
        self.progress = ttk.Progressbar(bar, maximum=100, length=180)
        self.progress.pack(side="right", padx=(0, 8))
        self.search_var.trace_add("write", lambda *_a: self.refresh_list())

        panes = ttk.PanedWindow(top, orient="vertical")
        panes.pack(fill="both", expand=True, padx=10)
        upper = ttk.Frame(panes)
        self.tree = ttk.Treeview(upper, columns=("english", "translation"), show="headings", selectmode="browse")
        self.tree.heading("english", text="English")
        self.tree.heading("translation", text="Translation")
        self.tree.column("english", width=width // 2 - 30, stretch=True)
        self.tree.column("translation", width=width // 2 - 30, stretch=True)
        self.tree.tag_configure("error", foreground="#b00000")
        self.tree.tag_configure("warning", foreground="#a05a00")
        self.tree.tag_configure("changed", background="#fff3c4")
        scroll = ttk.Scrollbar(upper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        panes.add(upper, weight=3)

        lower = ttk.Frame(panes, padding=(0, 6, 0, 0))
        panes.add(lower, weight=2)
        ttk.Label(lower, text="English:").grid(row=0, column=0, sticky="nw")
        self.english_text = tk.Text(lower, height=3, wrap="word", relief="solid", borderwidth=1,
                                    background="#f3f3f3")
        self.english_text.grid(row=0, column=1, sticky="we", pady=2)
        ttk.Label(lower, text="Translation:").grid(row=1, column=0, sticky="nw")
        self.edit = tk.Text(lower, height=3, wrap="word", relief="solid", borderwidth=1, undo=True)
        self.edit.grid(row=1, column=1, sticky="we", pady=2)
        for widget in (self.english_text, self.edit):
            widget.tag_configure("protected", background="#d8e8ff", foreground="#0b3d91")
        self.edit.bind("<<Modified>>", self._edited)
        self.context_var = tk.StringVar(master=top)
        ttk.Label(lower, textvariable=self.context_var, foreground="#555555", wraplength=width - 160,
                  justify="left").grid(row=2, column=1, sticky="w")
        self.problem_var = tk.StringVar(master=top)
        ttk.Label(lower, textvariable=self.problem_var, foreground="#a01010", wraplength=width - 160,
                  justify="left").grid(row=3, column=1, sticky="w", pady=(2, 0))
        ttk.Label(lower, text="Preview:").grid(row=4, column=0, sticky="nw", pady=(6, 0))
        preview_box = ttk.Frame(lower)
        preview_box.grid(row=4, column=1, sticky="we", pady=(6, 0))
        options = ttk.Frame(preview_box)
        options.pack(fill="x")
        self.font_var = tk.StringVar(master=top, value=FONT_CHOICES[0][0])
        font_box = ttk.Combobox(options, textvariable=self.font_var, values=[c[0] for c in FONT_CHOICES],
                                state="readonly", width=34)
        font_box.pack(side="left")
        font_box.bind("<<ComboboxSelected>>", lambda _e: self.update_preview())
        self.note_var = tk.StringVar(master=top)
        ttk.Label(options, textvariable=self.note_var, foreground="#555555").pack(side="left", padx=(10, 0))
        self.width_var = tk.StringVar(master=top)
        ttk.Label(preview_box, textvariable=self.width_var, foreground="#a05a00").pack(anchor="w")
        self.preview_frame = tk.Frame(preview_box, background=PREVIEW_BG, padx=6, pady=4)
        self.preview_frame.pack(fill="x", pady=(2, 0))
        lower.columnconfigure(1, weight=1)

        buttons = ttk.Frame(top, padding=10)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left")
        self.saved_var = tk.StringVar(master=top, value="Saved.")
        ttk.Label(buttons, textvariable=self.saved_var).pack(side="left", padx=(10, 0))
        ttk.Button(buttons, text="Close", command=self.close).pack(side="right")
        ttk.Label(buttons, text=str(self.path), foreground="#555555").pack(side="right", padx=(0, 12))

    # -- the list
    def _tags(self, key: str) -> tuple:
        issues = self.model.issues(key)
        if any(i.severity == "error" for i in issues):
            tags = ["error"]
        elif issues:
            tags = ["warning"]
        else:
            tags = []
        if key in self.model.changed:
            tags.append("changed")
        return tuple(tags)

    def refresh_list(self) -> None:
        keep = self.current
        self.tree.delete(*self.tree.get_children())
        for key in self.model.visible(self.search_var.get(), bool(self.untranslated_var.get())):
            row = self.model.row(key)
            self.tree.insert("", "end", iid=key, values=(_one_line(row.english), _one_line(row.translation)),
                             tags=self._tags(key))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)

    def visible_keys(self) -> list[str]:
        return list(self.tree.get_children())

    def update_progress(self) -> None:
        coverage = self.model.coverage
        self.progress["value"] = coverage
        self.progress_var.set(f"{coverage:.0f}% done ({self.model.used} of {self.model.total} lines)")

    # -- the selected line
    def _selected(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection and selection[0] != self.current:
            self.show(selection[0])

    def show(self, key: str) -> None:
        self.current = key
        row = self.model.row(key)
        self.loading = True
        for widget, text in ((self.english_text, row.english), (self.edit, row.translation)):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
        self.english_text.configure(state="disabled")
        self.edit.edit_reset()
        self.edit.edit_modified(False)
        self.loading = False
        note = self.model.context.get(key) or ""
        if key in self.model.changed:
            note = ("The English of this line changed; the old translation is in its notes. " + note).strip()
        self.context_var.set(note)
        self._highlight()
        self._problems()
        self.update_preview()

    def _tokens(self, key: str):
        rules = self.model.rules.get(key)
        return tuple(rules.tokens) + tuple(rules.required_tokens) if rules else ()

    def _highlight(self) -> None:
        if self.current is None:
            return
        tokens = self._tokens(self.current)
        for widget in (self.english_text, self.edit):
            widget.tag_remove("protected", "1.0", "end")
            text = widget.get("1.0", "end-1c")
            for start, end in protected_spans(text, tokens):
                widget.tag_add("protected", f"1.0+{start}c", f"1.0+{end}c")

    def _problems(self) -> None:
        key = self.current
        if key is None:
            return
        row = self.model.row(key)
        lines = []
        missing = missing_placeholders(row.english, row.translation, self._tokens(key))
        if missing:
            lines.append("Missing from the translation: " + "  ".join(missing))
        for issue in self.model.issues(key):
            prefix = "Stays English: " if issue.severity == "error" else "Check: "
            lines.append(prefix + issue.message)
        self.problem_var.set("\n".join(lines))

    def _edited(self, _event=None) -> None:
        if not self.edit.edit_modified():
            return
        self.edit.edit_modified(False)
        if self.loading or self.current is None:
            return
        self.set_translation(self.current, self.edit.get("1.0", "end-1c"), from_box=True)

    def set_translation(self, key: str, text: str, from_box: bool = False) -> None:
        if not self.model.set(key, text):
            return
        if not from_box and key == self.current:
            self.show(key)
        if self.tree.exists(key):
            row = self.model.row(key)
            self.tree.item(key, values=(_one_line(row.english), _one_line(row.translation)), tags=self._tags(key))
        if key == self.current:
            self._highlight()
            self._problems()
            self._schedule_preview()
        self.update_progress()
        self.dirty = True
        self.saved_var.set("Not saved yet (saves by itself in a moment).")
        self._schedule_save()

    # -- saving
    def _schedule_save(self) -> None:
        if self.save_after is not None:
            try:
                self.top.after_cancel(self.save_after)
            except tk.TclError:
                pass
        self.save_after = self.top.after(AUTOSAVE_MS, self.save)

    def save(self) -> bool:
        if self.save_after is not None:
            try:
                self.top.after_cancel(self.save_after)
            except tk.TclError:
                pass
            self.save_after = None
        try:
            fmt.write_file(self.path, self.model.tf)
        except OSError as exc:
            self.saved_var.set(f"Not saved: {exc}")
            return False
        self.dirty = False
        try:
            self.saved_var.set("Saved.")
        except tk.TclError:
            pass
        if self.on_saved is not None:
            self.on_saved(self.path)
        return True

    def close(self) -> bool:
        """Close the editor; False when it stays open (its edits could not be saved and the player chose to
        keep it), so a window closing it must stay open too (Codex, #672)."""
        if self.dirty and not self.save():
            if not messagebox.askyesno(TITLE, "The translation could not be saved. Close anyway?",
                                       parent=self.top, default="no"):
                return False
        self.top.destroy()
        return True

    def _gone(self, event) -> None:
        """However the window goes, nothing it scheduled runs after it."""
        if event.widget is not self.top:
            return
        for after in (self.save_after, self.preview_after):
            if after is not None:
                try:
                    self.top.after_cancel(after)
                except tk.TclError:
                    pass
        self.save_after = self.preview_after = None

    # -- the preview
    def _schedule_preview(self) -> None:
        if self.preview_after is not None:
            try:
                self.top.after_cancel(self.preview_after)
            except tk.TclError:
                pass
        self.preview_after = self.top.after(250, self.update_preview)

    def _font(self) -> str:
        chosen = self.font_var.get()
        return next((ldw for label, ldw in FONT_CHOICES if label == chosen), FONT_CHOICES[0][1])

    def _game_font_ok(self):
        glyphs = _font_glyphs()
        if glyphs is None or self.images_dir is None or not self.images_dir.is_dir():
            return None
        return glyphs

    def measure(self, text: str) -> int:
        """The widest line of `text` in pixels: the game's own measure when the glyph module is there, else
        the stand-in font's."""
        font = self._font()
        glyphs = self._game_font_ok()
        widths = []
        for line in text.split("\n"):
            if glyphs is not None:
                try:
                    widths.append(glyphs.text_width(f"vv{self.number}", font, line, self.images_dir))
                    continue
                except Exception:  # noqa: BLE001 -- the stand-in measure instead
                    glyphs = None
            if font not in self.fonts:
                self.fonts[font] = tkfont.Font(root=self.top, font=TK_FONTS[font])
            widths.append(self.fonts[font].measure(line))
        return max(widths) if widths else 0

    def update_preview(self) -> None:
        self.preview_after = None
        for child in self.preview_frame.winfo_children():
            child.destroy()
        self.photos = []
        key = self.current
        if key is None:
            return
        row = self.model.row(key)
        rules = self.model.rules.get(key)
        code = self.model.tf.code or "en"
        variants = preview_variants(row.english, row.translation, code, rules)
        english_variants = preview_variants(row.english, "", "en", rules)
        glyphs = self._game_font_ok()
        font = self._font()
        game = f"vv{self.number}"
        drawn_in_game_font = glyphs is not None
        for label, text in variants:
            line = tk.Frame(self.preview_frame, background=PREVIEW_BG)
            line.pack(anchor="w", fill="x")
            if label:
                tk.Label(line, text=label + ":", background=PREVIEW_BG, foreground="#d9c9a8",
                         font=("Segoe UI", 8)).pack(side="left", anchor="n", padx=(0, 6))
            shown = False
            if glyphs is not None:
                holder = tk.Frame(line, background=PREVIEW_BG)
                try:
                    for piece in text.split("\n"):
                        image = glyphs.render_text(game, font, piece, self.images_dir)
                        photo = image.photo(tk, self.top)
                        self.photos.append(photo)
                        tk.Label(holder, image=photo, background=PREVIEW_BG, borderwidth=0).pack(anchor="w")
                    holder.pack(side="left", anchor="w")
                    shown = True
                except Exception:  # noqa: BLE001 -- the plain preview instead
                    drawn_in_game_font = False
                    holder.destroy()
            if not shown:
                tk.Label(line, text=text, background=PREVIEW_BG, foreground="#ffffff", font=TK_FONTS[font],
                         justify="left", anchor="w").pack(side="left", anchor="w")
        if drawn_in_game_font:
            self.note_var.set("Drawn in the game's own letters.")
        elif _font_glyphs() is not None and (self.images_dir is None or not self.images_dir.is_dir()):
            self.note_var.set("Plain preview: the game's folder (its Images) was not found.")
        else:
            self.note_var.set("Plain preview (" + GAME_FONT_NOTE + ").")
        warning = ""
        if row.translation:
            try:
                english_width = max(self.measure(t) for _l, t in english_variants)
                width = max(self.measure(t) for _l, t in variants)
            except (tk.TclError, ValueError):
                english_width = width = 0
            if width > english_width * WIDE_RATIO and width > english_width + WIDE_MARGIN:
                warning = (f"Much wider than the English ({width} px against {english_width} px): it "
                           f"{TOO_WIDE}.")
        self.width_var.set(warning)


# ---- choosing a language to make -----------------------------------------------------------------------------

def language_labels() -> list[str]:
    return [f"{native} ({code}) - {english}" for code, native, english in fmt.LANGUAGES] + [OTHER_LANGUAGE]


def language_for_label(label: str) -> tuple[str, str] | None:
    for code, native, english in fmt.LANGUAGES:
        if label == f"{native} ({code}) - {english}":
            return native, code
    return None


_CODE_RE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")


def other_language_problem(name: str, code: str) -> str | None:
    name, code = name.strip(), code.strip()
    if not name:
        return "Type the language's own name (for example Français)."
    if fmt.find_emails(name) or fmt.find_emails(code) or "@" in name:
        return fmt.EMAIL_SENTENCE
    if not _CODE_RE.fullmatch(code):
        return "Type a language code such as fr, tr, ja or zh-Hans."
    return None


def ask_language(parent) -> tuple[str, str] | None:
    """(the language's own name, its code), or None."""
    top = tk.Toplevel(parent)
    top.title("Make a translation")
    if parent is not None:
        top.transient(parent)
    result: dict = {"value": None}
    frame = ttk.Frame(top, padding=14)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Which language? Each is listed by its own name and code.").pack(anchor="w")
    box = ttk.Frame(frame)
    box.pack(fill="both", expand=True, pady=(6, 0))
    listbox = tk.Listbox(box, height=min(16, max(8, top.winfo_screenheight() // 60)), width=46,
                         exportselection=False)
    bar = ttk.Scrollbar(box, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)
    for label in language_labels():
        listbox.insert("end", label)
    other = ttk.Frame(frame)
    name_var, code_var, problem_var = (tk.StringVar(master=top) for _ in range(3))
    ttk.Label(other, text="Language's own name:").grid(row=0, column=0, sticky="w")
    ttk.Entry(other, textvariable=name_var, width=28).grid(row=0, column=1, sticky="w", pady=2)
    ttk.Label(other, text="Language code:").grid(row=1, column=0, sticky="w")
    ttk.Entry(other, textvariable=code_var, width=12).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frame, textvariable=problem_var, foreground="#a01010").pack(anchor="w")
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e", side="bottom", pady=(10, 0))

    def picked_other() -> bool:
        sel = listbox.curselection()
        return bool(sel) and listbox.get(sel[0]) == OTHER_LANGUAGE

    def changed(_event=None) -> None:
        if picked_other():
            other.pack(anchor="w", pady=(6, 0), before=buttons)
        else:
            other.pack_forget()

    def ok(_event=None) -> None:
        sel = listbox.curselection()
        if not sel:
            problem_var.set("Choose a language.")
            return
        if picked_other():
            problem = other_language_problem(name_var.get(), code_var.get())
            if problem:
                problem_var.set(problem)
                return
            result["value"] = (name_var.get().strip(), code_var.get().strip())
        else:
            result["value"] = language_for_label(listbox.get(sel[0]))
        top.destroy()

    ttk.Button(buttons, text="OK", command=ok).pack(side="left")
    ttk.Button(buttons, text="Cancel", command=top.destroy).pack(side="left", padx=(8, 0))
    listbox.bind("<<ListboxSelect>>", changed)
    listbox.bind("<Double-Button-1>", ok)
    top.bind("<Escape>", lambda _e: top.destroy())
    try:
        top.grab_set()
    except tk.TclError:
        pass
    top.wait_window()
    return result["value"]


# ---- Download from GitHub... -----------------------------------------------------------------------------------

DOWNLOAD_TITLE = "Download from GitHub"
DOWNLOAD_NOTE = ("The translations shared on the patcher's GitHub page (its public translations folder). Only "
                 "files that passed the VirusTotal scan and the translation check are listed. Nothing is sent: "
                 "the list is read without a login.")


def download_selected(number: int, client, remotes, check=None) -> tuple[list[Path], list[str]]:
    """Each chosen remote file downloaded, checked as data and installed like Add translation file....
    (installed, problems)."""
    check = check or (lambda path: check_translation(path, number))
    done, problems = [], []
    for remote in remotes:
        try:
            data = client.fetch(remote)
            done.append(vv_translations_github.install(remote, data, check))
        except vv_translations_github.RemoteError as error:
            problems.append(str(error))
    return done, problems


class DownloadDialog:
    def __init__(self, window, client):
        self.window, self.client = window, client
        self.number = window.number
        self.remotes: list = []
        top = self.top = tk.Toplevel(window.top)
        top.title(f"{DOWNLOAD_TITLE} - {tr.TITLES[self.number]}")
        top.transient(window.top)
        frame = ttk.Frame(top, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=DOWNLOAD_NOTE, wraplength=620, justify="left").pack(anchor="w")
        self.tree = ttk.Treeview(frame, columns=("language", "credit", "changed", "status"), show="headings",
                                 selectmode="extended", height=12)
        for column, text, width in (("language", "Language", 170), ("credit", "Credit", 200),
                                    ("changed", "Last changed", 110), ("status", "Status", 160)):
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=(8, 0))
        for key in ("<Control-a>", "<Control-A>"):
            self.tree.bind(key, self.select_all)
        self.status_var = tk.StringVar(master=top)
        ttk.Label(frame, textvariable=self.status_var, wraplength=620, justify="left",
                  foreground="#245a9a").pack(anchor="w", pady=(6, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Select All", command=self.select_all).pack(side="left")
        ttk.Button(buttons, text="Download", command=self.download).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=self.close).pack(side="right")
        top.bind("<Escape>", lambda _e: self.close())
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.download = self
        try:
            top.grab_set()
        except tk.TclError:
            pass
        self.refresh()

    def refresh(self) -> None:
        self.status_var.set("Reading the list from GitHub...")
        try:
            self.top.update_idletasks()
        except tk.TclError:
            pass
        try:
            self.remotes = self.client.list_game(self.number)
        except vv_translations_github.RemoteError as error:
            self.remotes = []
            self.status_var.set(str(error))
        else:
            self.status_var.set(f"{len(self.remotes)} translation(s) on GitHub." if self.remotes else
                                "There is no translation of this game on GitHub yet.")
        self.tree.delete(*self.tree.get_children())
        for n, remote in enumerate(self.remotes):
            self.tree.insert("", "end", iid=str(n), values=(remote.language, remote.translator or "-",
                                                             remote.changed_text, remote.status))

    def rows(self) -> list[tuple]:
        return [tuple(self.tree.item(i, "values")) for i in self.tree.get_children()]

    def select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def selected(self) -> list:
        return [self.remotes[int(i)] for i in self.tree.selection()]

    def download(self):
        chosen = self.selected()
        if not chosen:
            self.status_var.set("Select the translations to download (Ctrl+click or Shift+click for several).")
            return [], []
        done, problems = download_selected(self.number, self.client, chosen)
        self.window.load()
        if done:
            self.window.reapply_all(done)
        vv_translations_github.mark_status(self.number, self.remotes)
        for n, remote in enumerate(self.remotes):
            self.tree.set(str(n), "status", remote.status)
        text = f"Downloaded and installed {len(done)} file(s)." if done else "Nothing was installed."
        if problems:
            text += " " + " ".join(problems)
        self.status_var.set(text)
        self.window._say(text)
        return done, problems

    def close(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        self.window._regrab()


# ---- the window ----------------------------------------------------------------------------------------------

class TranslationsWindow:
    def __init__(self, app, build=None):
        self.app = app
        builds = list(getattr(app, "builds", []) or [])
        self.titles = [b.title for b in builds] or [tr.TITLES[n] for n in sorted(tr.TITLES)]
        start = build.title if build is not None else self.titles[0]
        top = self.top = tk.Toplevel(app)
        top.title(TITLE)
        top.transient(app)
        try:
            from vv_tree_editor_tools import scrollable_frame
            frame = scrollable_frame(top, padding=16)
        except ImportError:
            frame = ttk.Frame(top, padding=16)
            frame.pack(fill="both", expand=True)
        self.frame = frame
        self.editor: Editor | None = None
        self.entries: list[tuple[str, Path | None]] = []
        self.files: list[tr.Installed] = []
        ttk.Label(frame, text=(
            "Plays a patched game in another language, and lets you make, add and share translations. Lines a "
            "translation leaves out, or gets wrong, stay English."), wraplength=600, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.game_var = tk.StringVar(master=top, value=start)
        ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w")
        game_box = ttk.Combobox(frame, textvariable=self.game_var, values=self.titles, state="readonly", width=48)
        game_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
        game_box.bind("<<ComboboxSelected>>", lambda _e: self.load())
        ttk.Label(frame, text="Language:").grid(row=2, column=0, sticky="w")
        self.language_var = tk.StringVar(master=top)
        self.language_box = ttk.Combobox(frame, textvariable=self.language_var, state="readonly", width=48)
        self.language_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=2)
        self.language_box.bind("<<ComboboxSelected>>", lambda _e: self.choose(self.language_box.current()))
        ttk.Label(frame, text=PATCH_ROW_NOTE, wraplength=600, justify="left", foreground="#555555").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self.status_var = tk.StringVar(master=top)
        ttk.Label(frame, textvariable=self.status_var, wraplength=600, justify="left", foreground="#245a9a").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        files = ttk.LabelFrame(frame, text="Translation files", padding=10)
        files.grid(row=5, column=0, columnspan=3, sticky="we", pady=(12, 0))
        ttk.Label(files, text="Files:").grid(row=0, column=0, sticky="nw")
        # Several can be selected: a click selects one, Ctrl+click adds or removes one, Shift+click a range,
        # Ctrl+A (or Select All) every one.
        list_frame = ttk.Frame(files)
        list_frame.grid(row=0, column=1, sticky="we", pady=2)
        self.file_list = tk.Listbox(list_frame, selectmode="extended", height=6, width=52, exportselection=False,
                                    activestyle="dotbox")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        for key in ("<Control-a>", "<Control-A>"):
            self.file_list.bind(key, self.select_all)
        self.file_list.bind("<Delete>", lambda _e: self.delete())
        row1 = ttk.Frame(files)
        row1.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(row1, text="Make a translation...", command=self.make).pack(side="left")
        ttk.Button(row1, text="Edit...", command=self.edit_selected).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Add translation file...", command=self.add_dialog).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text=DOWNLOAD_TITLE + "...", command=self.download_dialog).pack(side="left", padx=(8, 0))
        row2 = ttk.Frame(files)
        row2.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(row2, text="Select All", command=self.select_all).pack(side="left")
        ttk.Button(row2, text="Export...", command=self.export).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Delete...", command=self.delete).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Share on GitHub...", command=self.share).pack(side="left", padx=(8, 0))
        ttk.Label(files, text=SHARE_SENTENCE + "\n" + SHARE_HOW, wraplength=580, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.drop_var = tk.StringVar(master=top)
        ttk.Label(files, textvariable=self.drop_var, foreground="#555555").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        files.columnconfigure(1, weight=1)
        ttk.Button(frame, text="Close", command=self.close).grid(row=6, column=2, sticky="e", pady=(12, 0))
        frame.columnconfigure(1, weight=1)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Escape>", lambda _e: self.close())
        top.translations = self
        self.drop = DropTarget(top, self.add_paths)
        self.load()
        top.update_idletasks()
        if self.drop.install():
            self.drop_var.set("You can also drag a translation file onto this window to add it.")
        try:
            top.grab_set()
        except tk.TclError:
            pass

    # -- state
    @property
    def number(self) -> int:
        title = self.game_var.get()
        # By title here: vv_translations.game_number reads a str's own .title method for a title string.
        return next((n for n, t in tr.TITLES.items() if t.casefold() == title.casefold()), 1)

    def load(self) -> None:
        number = self.number
        installed = tr.installed(number)
        self.files = installed
        self.entries = [(tr.ENGLISH, None)] + [(item.label, item.path) for item in installed]
        self.language_box.configure(values=[label for label, _p in self.entries])
        chosen = chosen_path(self.app, number)
        index = 0
        for n, (_label, path) in enumerate(self.entries):
            if path is not None and chosen is not None and path.name == chosen.name:
                index = n
        self.language_box.current(index)
        # The file list: English (original) first (never a file: Delete... and Export... skip it), then every
        # installed translation; the game's chosen one is selected, else the first translation.
        self.file_list.delete(0, "end")
        for label, _path in self.entries:
            self.file_list.insert("end", label)
        keep = next((n + 1 for n, item in enumerate(installed) if chosen is not None
                     and item.path.name == chosen.name), 1 if installed else 0)
        self.file_list.selection_set(keep)
        self.file_list.activate(keep)
        self.file_list.see(keep)

    def language_labels(self) -> list[str]:
        return [label for label, _p in self.entries]

    def file_labels(self) -> list[str]:
        return list(self.file_list.get(0, "end"))

    def selected_entries(self) -> list[Path | None]:
        """The selected rows of the file list, in list order: a file's path, None for English (original)."""
        return [self.entries[int(i)][1] for i in self.file_list.curselection() if 0 <= int(i) < len(self.entries)]

    def selected_files(self) -> list[Path]:
        return [p for p in self.selected_entries() if p is not None]

    def selected_file(self) -> Path | None:
        """The one file Edit... and Share on GitHub... use: the first selected translation."""
        files = self.selected_files()
        return files[0] if files else None

    def select(self, labels) -> None:
        """Select exactly the rows with these labels (as clicking and Ctrl+clicking them does)."""
        self.file_list.selection_clear(0, "end")
        for n, label in enumerate(self.file_labels()):
            if label in labels:
                self.file_list.selection_set(n)

    def select_all(self, _event=None):
        self.file_list.selection_set(0, "end")
        return "break"

    def _say(self, text: str) -> None:
        self.status_var.set(text)
        status = getattr(self.app, "status_var", None)
        if status is not None:
            try:
                status.set(f"{TITLE}: {text}")
            except (tk.TclError, AttributeError):
                pass

    def _regrab(self) -> None:
        try:
            if self.top.winfo_exists():
                self.top.grab_set()
        except tk.TclError:
            pass

    def _ask_patched_folder(self, number: int) -> Path | None:
        title = tr.TITLES[number]
        messagebox.showinfo(TITLE, (
            f"No patched copy of {title} was found. {PATCH_ROW_NOTE}\n\nChoose the patched game's folder (the "
            f"one with the \"{tr.PATCHER_FILES}\" folder)."), parent=self.top)
        chosen = filedialog.askdirectory(parent=self.top, title=f"Choose the patched {title} folder",
                                         mustexist=True)
        self._regrab()
        if not chosen:
            return None
        folder = Path(chosen)
        if not (folder / tr.PATCHER_FILES).is_dir():
            messagebox.showerror(TITLE, (
                f"{folder} is not a patched game (it has no \"{tr.PATCHER_FILES}\" folder). Patch the game with "
                "the Translations row first (it is on by default)."), parent=self.top)
            return None
        remember_folder(self.app, number, folder)
        return folder

    # -- the Language list
    def choose(self, index: int, ask_folder: bool = True) -> list[Path]:
        if not 0 <= index < len(self.entries):
            return []
        number = self.number
        label, path = self.entries[index]
        remember_choice(self.app, number, path)
        folders = patched_folders(self.app, number)
        if path is not None and not folders and ask_folder:
            folder = self._ask_patched_folder(number)
            folders = [folder] if folder else []
        done, problems = apply_to_games(number, path, folders)
        short = tr.TITLES[number].removeprefix("Virtual Villagers - ")
        if done:
            places = "; ".join(str(f) for f in done)
            self._say(f"{short} will be in {label} from its next start ({places}).")
        elif path is None:
            self._say(f"{short} will be in English.")
        else:
            self._say(f"{label} is remembered for {short}; no patched copy of the game was found yet. Every copy "
                      "you patch from now on uses it.")
        if problems:
            messagebox.showerror(TITLE, "Could not update:\n\n" + "\n".join(problems), parent=self.top)
        return done

    def reapply_all(self, paths) -> None:
        for path in paths:
            self.reapply(path)

    def reapply(self, path: Path) -> None:
        """The editor saved `path`: a game that uses it gets the new text from its next start."""
        number = self.number
        chosen = chosen_path(self.app, number)
        if chosen is not None and Path(path).name == chosen.name:
            apply_to_games(number, chosen, patched_folders(self.app, number))
            tr.set_display_choice(number, chosen)

    # -- making and editing
    def _template(self, number: int, ask: bool = True):
        """(rows, game folder) read from the player's own game; asks for the folder when none is known."""
        folders = template_folders(self.app, number)
        if not folders and ask:
            title = tr.TITLES[number]
            chosen = filedialog.askdirectory(
                parent=self.top, mustexist=True,
                title=f"Choose the {title} folder (the one with the game's .exe)")
            self._regrab()
            if not chosen:
                return None, None
            folders = [Path(chosen)]
        for folder in folders:
            exe = find_exe(folder, number)
            if exe is None:
                continue
            try:
                return tr.template_rows(number, exe=exe), folder
            except (OSError, ValueError, KeyError, struct.error) as exc:
                messagebox.showerror(TITLE, f"The game's text could not be read from {exe}: {exc}",
                                     parent=self.top)
                return None, None
        if ask:
            messagebox.showerror(TITLE, f"No {tr.TITLES[number]} game was found in that folder.", parent=self.top)
        return None, None

    def make(self) -> None:
        language = ask_language(self.top)
        self._regrab()
        if language is None:
            return
        name, code = language
        self.open_editor(name, code)

    def edit_selected(self) -> None:
        path = self.selected_file()
        if path is None:
            messagebox.showinfo(TITLE, "There is no translation for this game yet. Use Make a translation...",
                                parent=self.top)
            return
        try:
            tf = fmt.read_file(path)
        except (OSError, fmt.FormatError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.top)
            return
        self.open_editor(tf.language, tf.code, path)

    def open_editor(self, language: str, code: str, path: Path | None = None, rows=None,
                    folder: Path | None = None) -> Editor | None:
        number = self.number
        if rows is None:
            rows, folder = self._template(number)
            if rows is None:
                return None
        if path:
            target = Path(path)
        else:
            same = [i.path for i in tr.installed(number) if i.code.casefold() == code.casefold()]
            try:
                target = same[0] if same else tr.game_dir(number) / tr.installed_name(code)
            except fmt.FormatError as exc:
                messagebox.showerror(TITLE, str(exc), parent=self.top)
                return None
        changed: set = set()
        if target.is_file():
            try:
                old = fmt.read_file(target)
            except (OSError, fmt.FormatError) as exc:
                messagebox.showerror(TITLE, f"{target.name} cannot be read: {exc}", parent=self.top)
                return None
            tf, status = fmt.update(old, [r.row for r in rows])
            changed = {key for key, value in status.items() if value == "changed"}
        else:
            tf = tr.new_translation(number, language, code, rows)
            try:
                fmt.write_file(target, tf)
            except OSError as exc:
                messagebox.showerror(TITLE, f"The file could not be made: {exc}", parent=self.top)
                return None
            self.load()
        images = Path(folder) / "Images" if folder else None
        self.editor = Editor(self.top, number, target, tf, rows, images_dir=images, on_saved=self._saved,
                             changed=changed)
        try:
            self.editor.top.grab_set()
        except tk.TclError:
            pass
        return self.editor

    def _saved(self, path: Path) -> None:
        self.reapply(path)
        try:
            keep = self.language_box.current()
            self.load()
            if 0 <= keep < len(self.entries):
                self.language_box.current(keep)
        except tk.TclError:
            pass

    # -- adding, exporting, sharing
    def add_dialog(self) -> None:
        chosen = filedialog.askopenfilenames(parent=self.top, title="Add translation file",
                                             filetypes=[("Translation files", "*.tsv *.txt"), ("All files", "*.*")])
        self._regrab()
        if chosen:
            self.add_paths(list(chosen))

    def add_paths(self, paths) -> list[Path]:
        number = self.number
        template = None
        rows, _folder = self._template(number, ask=False)
        if rows:
            template = tr.template_map(rows)
        added = []
        for raw in paths:
            path = Path(raw)
            checked = check_translation(path, number, template)
            if not checked.ok:
                messagebox.showerror(TITLE, f"{path.name}\n\n" + report_text(checked), parent=self.top)
                continue
            try:
                target = tr.install_target(number, checked.tf)
            except fmt.FormatError as exc:
                messagebox.showerror(TITLE, f"{path.name}\n\n{exc}", parent=self.top)
                continue
            if target.exists() and target.resolve() != path.resolve():
                if not vv_copy_slot_window.ask_yes_no(
                        self.top, TITLE, f"A {checked.tf.language} ({checked.tf.code}) translation is already "
                                         f"in the list. Replace it with {path.name}?"):
                    continue
            try:
                installed, checked = add_translation(number, path, template)
            except (OSError, fmt.FormatError) as exc:
                messagebox.showerror(TITLE, f"{path.name} could not be added: {exc}", parent=self.top)
                continue
            if installed is None:
                continue
            added.append(installed)
            messagebox.showinfo(TITLE, f"{path.name} was added.\n\n" + report_text(checked), parent=self.top)
            self.reapply(installed)
        self._regrab()
        if added:
            self.load()
            self._say(f"Added {', '.join(p.name for p in added)}.")
        return added

    def export(self):
        """Export...: one selected file to a name the player chooses; several, each under its own name, into a
        folder the player chooses.  English (original) is not a file and is skipped.  The exported path (one
        file), the list of exported paths (several) or None."""
        paths = self.selected_files()
        if not paths:
            text = ("There is no translation for this game to export yet." if not self.files else
                    f"Select the translations to export. {tr.ENGLISH} is the game's own text and is not a file.")
            messagebox.showinfo(TITLE, text, parent=self.top)
            return None
        number = self.number
        if len(paths) > 1:
            chosen = filedialog.askdirectory(parent=self.top, mustexist=True,
                                             title=f"Choose the folder to export {len(paths)} translations to")
            self._regrab()
            if not chosen:
                return None
            done, problems = tr.export_many(paths, Path(chosen))
            if problems:
                messagebox.showerror(TITLE, "Not exported:\n\n" + "\n".join(problems), parent=self.top)
            if done:
                self._say(f"Exported {len(done)} files to {chosen}.")
            return done
        path = paths[0]
        try:
            language = fmt.read_file(path).language
        except (OSError, fmt.FormatError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.top)
            return None
        chosen = filedialog.asksaveasfilename(
            parent=self.top, title="Export translation", initialfile=export_name(number, language),
            defaultextension=".txt", filetypes=[("Translation files", "*.txt")])
        self._regrab()
        if not chosen:
            return None
        try:
            target = export_translation(path, Path(chosen))
        except OSError as exc:
            messagebox.showerror(TITLE, f"Not exported: {exc}", parent=self.top)
            return None
        self._say(f"Exported {target}.")
        return target

    def download_dialog(self, client=None):
        """Download from GitHub...: the public folder's scanned translations of this game, several selectable."""
        dialog = DownloadDialog(self, client or vv_translations_github.Client())
        return dialog

    def delete(self, *, ask=None, shell=None):
        """Delete...: every selected translation to the Recycle Bin after one Yes / No question (No the default).
        English (original) is skipped and named.  An editor open on a deleted file is closed without saving.
        (deleted, problems), or None when nothing was done."""
        entries = self.selected_entries()
        number = self.number
        if not any(p is not None for p in entries):
            messagebox.showinfo(DELETE_TITLE, ENGLISH_KEPT if entries else "Select the translations to delete.",
                                parent=self.top)
            return None
        result = delete_translations(self.app, number, entries, ask=ask, shell=shell, parent=self.top)
        self._regrab()
        if result is None:
            return None
        deleted, problems = result
        gone = {os.path.normcase(str(p)) for p in deleted}
        editor = self.editor
        if editor is not None and os.path.normcase(str(editor.path)) in gone:
            try:
                if editor.top.winfo_exists():
                    editor.dirty = False
                    editor.top.destroy()
            except tk.TclError:
                pass
            self.editor = None
        self.load()
        if deleted:
            self._say(f"Moved {', '.join(p.name for p in deleted)} to the Recycle Bin.")
        if problems:
            messagebox.showerror(DELETE_TITLE, "\n\n".join(problems), parent=self.top)
        return deleted, problems

    def share(self) -> Path | None:
        path = self.selected_file()
        if path is None:
            messagebox.showinfo(TITLE, "There is no translation for this game to share yet. Use Make a "
                                       "translation... or Add translation file... first.", parent=self.top)
            return None
        if self.editor is not None and self.editor.top.winfo_exists() and self.editor.dirty:
            self.editor.save()
        number = self.number
        rows, _folder = self._template(number, ask=False)
        target = share_on_github(self.top, number, path, template=tr.template_map(rows) if rows else None)
        self._regrab()
        if target is not None:
            self.load()
            self._say(f"Saved {target.name} for sharing; drag it into the GitHub page and press Submit.")
        return target

    def close(self) -> bool:
        """Close the window and its editor; False (both stay open) when the editor's unsaved edits are kept."""
        if self.editor is not None:
            try:
                if self.editor.top.winfo_exists() and not self.editor.close():
                    return False
            except tk.TclError:
                pass
        self.drop.remove()
        self.top.destroy()
        return True


def open_translations(app, build=None) -> tk.Toplevel:
    """The Translations window, for ``build`` (the One Game tab's game) or, with None, the first of the five."""
    return TranslationsWindow(app, build).top
