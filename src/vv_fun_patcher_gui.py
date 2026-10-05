from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from transparency import PATCHER_VERSION
import vv_log_tools
import vv_save_backup
import vv_tribe_rename

# Link colours: the resting blue and the hover red.
LINK_COLOR = "#0645ad"
LINK_HOVER_COLOR = "#c5350b"

from vv_fun_patcher import (
    patch_requirement_text,
    unmet_needs_on_text,
    DEFAULT_PATCH_MODE,
    _validate_public_patch_mode,
    PatcherError,
    apply_all,
    apply_patch,
    dry_run,
    dry_run_all,
    get_patch_mode,
    get_patch_variant,
    identify,
    load_builds,
    load_public_fun_patches,
    load_patch_modes,
    resolve_fun_patch_ids,
    validate_all_sources,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "patcher_local_settings.json"
# The setting beside Check Logs / Repair Logs (STARTUP_LOADER_CHECK_LOGS in
# vv_fun_patcher.py): off by default, remembered, written into every game the
# window creates from then on.
CHECK_LOGS_LABEL = (
    "Check logs automatically (games created from now on check each village "
    "silently and, only if something is wrong, ask Repair / Not now when you "
    "close the game)"
)

# Patches the default selection leaves OFF.
#
# The owner's rule: the defaults select every patch except Learning Skills
# Never Fails, in all five games. Everything else is on, so this is a
# deny-list rather than an allow-list -- a new patch is included in the
# defaults automatically, which is what the "all patches on by default"
# requirement means, and only a patch named here is held back.
#
# Matched by exact id rather than by substring or display name, so a future
# patch whose name merely mentions learning is not excluded by accident.
DEFAULT_OFF_FUN_PATCH_IDS = frozenset(
    ["vv%d_learning_never_fails" % game for game in range(1, 6)]
    # The owner: VV1 Mushroom/Collectible Duplication Cheat (VV2-VV5) is a default-off patch.
    + ["vv%d_everyone_collects_like_vv1" % game for game in range(2, 6)]
    # The owner: Super-Secret Golden Mushroom (all five games) is default-off.
    + ["vv%d_super_secret_golden_mushroom" % game for game in range(1, 6)]
    # The owner: Manual Drop-Breeding overrides Birth Control (all five games)
    # is "Default-OFF. Owner's-Defaults ON."
    + ["vv%d_manual_drop_breeding_overrides_birth_control" % game for game in range(1, 6)]
    # The owner: Story / Cheat Upgrades (all five games) is off by default;
    # Owner's Defaults ticks it (owner, 2026-10-03).
    + ["vv%d_story_cheat_upgrades" % game for game in range(1, 6)]
    # 256 Villagers (Experimental) is off by default: it moves the villager
    # table and changes the save format. Owner's Defaults ticks it (owner,
    # 2026-10-03); Select All does not (SELECT_ALL_OFF_FUN_PATCH_IDS).
    + ["vv3_population_256", "vv4_population_256", "vv5_population_256"]
)

# Patches the Owner's Defaults button leaves OFF, by exact id.  Owner's
# Defaults ticks every other default-off patch; the one exception the owner
# named is Learning Skills Never Fails.  (2026-10-03: "please toggle ON in the
# Owner's Defaults: 256 experimental patches, Story events patches.")
OWNERS_DEFAULT_OFF_FUN_PATCH_IDS = frozenset(
    ["vv%d_learning_never_fails" % game for game in range(1, 6)]
)

# Patches even Select All Patches leaves OFF, by exact id.  The owner: Select
# All must not tick 256 Villagers (Experimental) -- it turns the build into a
# separate "- Modded 256" game with its own save folder and save format.
SELECT_ALL_OFF_FUN_PATCH_IDS = frozenset(
    ["vv3_population_256", "vv4_population_256", "vv5_population_256"]
)


def select_all_fun_patch_selection(patch_id: str) -> bool:
    """Whether the Select All Patches button ticks this."""
    return patch_id not in SELECT_ALL_OFF_FUN_PATCH_IDS


def default_fun_patch_selection(patch_id: str) -> bool:
    """Whether a fresh install, or the Default Patches button, ticks this."""
    return patch_id not in DEFAULT_OFF_FUN_PATCH_IDS


def split_bold(text: str) -> list[tuple[str, bool]]:
    """Split a description at its **bold** markers: [(segment, is_bold), ...].

    The owner: descriptions state dependencies in **bold**, and the patcher
    must show them bold, not as literal asterisks.  An unmatched trailing
    marker is kept as text rather than swallowing the rest of the line.
    """
    parts = text.split("**")
    if len(parts) % 2 == 0:            # odd number of markers: the last is literal
        parts[-2:] = [parts[-2] + "**" + parts[-1]]
    return [(part, index % 2 == 1) for index, part in enumerate(parts) if part]


class RichDescription(tk.Text):
    """A read-only, auto-height text block that shows **bold** segments bold."""

    def __init__(self, parent, text: str, width_px: int, bold_font, normal_font, background):
        super().__init__(parent, wrap="word", borderwidth=0, highlightthickness=0,
                         padx=0, pady=0, cursor="arrow", font=normal_font, background=background,
                         height=1, width=max(20, width_px // max(1, normal_font.measure("0"))))
        self.tag_configure("bold", font=bold_font)
        for segment, bold in split_bold(text):
            self.insert("end", segment, ("bold",) if bold else ())
        self.configure(state="disabled")
        self.bind("<Configure>", lambda _event: self._fit())

    def _fit(self) -> None:
        lines = self.count("1.0", "end", "displaylines")
        count = lines[0] if isinstance(lines, tuple) else lines
        if count and int(self.cget("height")) != count:
            self.configure(height=count)


def owners_default_fun_patch_selection(patch_id: str) -> bool:
    """Whether the Owner's Defaults button ticks this.

    The owner: "Every patch EXCEPT FOR LEARNING NEVER FAILS is on." -- so the
    other default-off patches are ticked here too, Story / Cheat Upgrades and
    256 Villagers (Experimental) included.  Matched by exact id.
    """
    return patch_id not in OWNERS_DEFAULT_OFF_FUN_PATCH_IDS


# The owner: the update link opens the project's base GitHub
# repository, not the releases page. It opens the page rather than querying an
# API and reporting a comparison.
RELEASES_PAGE = "https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/"
# How long to keep retrying the wait window's modal grab before giving up, and
# how long to wait between attempts. Two seconds is far longer than a window
# manager needs to make a window viewable, so exhausting it means something is
# genuinely wrong rather than merely slow.
GRAB_TIMEOUT_SECONDS = 2.0
GRAB_POLL_SECONDS = 0.03


def group_fun_patches(builds, patches):
    """Return deterministic game headers and patch catalogs for the chooser.

    Build order is the manifest order, not alphabetical.  Unknown or shared
    entries are kept under one final header so the presentation cannot drift
    when a new optional feature is added.
    """
    game_order = {build.id: index for index, build in enumerate(builds)}
    ordered = sorted(
        patches,
        key=lambda patch: (
            game_order.get(patch.game_id, len(game_order)),
            patch.name.casefold(),
            patch.id,
        ),
    )
    grouped = {build.id: [] for build in builds}
    shared = []
    for patch in ordered:
        if patch.game_id in grouped:
            grouped[patch.game_id].append(patch)
        else:
            shared.append(patch)
    headers = [
        (build.title, sorted(grouped[build.id], key=lambda item: (item.name.casefold(), item.id)))
        for build in builds
        if grouped[build.id]
    ]
    if shared:
        headers.append(
            (
                "Shared / All Games",
                sorted(shared, key=lambda item: (item.name.casefold(), item.id)),
            )
        )
    return headers


WAIT_POLL_SECONDS = 0.03


def centered_origin(parent_rect, size, screen):
    """Top-left corner for a window of ``size`` centred on ``parent_rect``.

    ``parent_rect`` is ``(x, y, w, h)`` in virtual-desktop coordinates, or None
    when the parent is not viewable.

    The parent-relative result must NOT be clamped to zero. On a multi-monitor
    desktop, a window on a screen positioned left of or above the primary
    display has legitimately NEGATIVE root coordinates, and clamping throws the
    child onto the primary monitor. For the wait window that is the worst
    possible failure: it holds a modal grab, so the application appears locked
    while the thing explaining why sits on a screen the user may not be looking
    at -- exactly the "looks like a crash" impression the window exists to
    prevent.

    Only the screen-centred fallback is clamped, because there a negative value
    really would be off-screen.
    """
    width, height = size
    if parent_rect is not None:
        px, py, pwidth, pheight = parent_rect
        return px + (pwidth - width) // 2, py + (pheight - height) // 2
    swidth, sheight = screen
    return max(0, (swidth - width) // 2), max(0, (sheight - height) // 2)



def _documents_folder() -> Path:
    """The Documents folder Windows actually resolves, not a home-relative guess.

    The exporters call SHGetFolderPathA(CSIDL_PERSONAL) (see
    native/shared/save_folder.c), which follows the Known Folder redirection a
    player may have to OneDrive or a corporate share. Path.home()/"Documents"
    ignores that redirection, so on a redirected account the completion dialog
    named a folder the logs are never written to -- the same class of mistake
    as pointing at the install directory, one layer down. Found in review.

    Falls back to the literal only when the shell call is unavailable, which
    is the best guess left rather than no path at all.
    """
    try:
        import ctypes
        import ctypes.wintypes
        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
        ) == 0 and buf.value:
            return Path(buf.value)
    except (OSError, AttributeError, ImportError):
        pass
    return Path.home() / "Documents"


class WaitWindow:
    """A small "Please wait..." window shown over blocking work.

    The patcher copies whole game folders and renders patched bytes on the Tk
    main thread, so the main window stops repainting and Windows relabels it
    "(Not Responding)".  Nothing is wrong when that happens, but it reads as a
    crash.  This gives the wait a face that says so.
    """

    def __init__(self, parent, title: str, message: str, modal: bool = True) -> None:
        self._parent = parent
        self._modal = modal
        window = tk.Toplevel(parent)
        self._window = window
        window.title(title)
        window.resizable(False, False)
        # The work cannot be cancelled partway without leaving a half-copied
        # game folder behind, so the close button does nothing.
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        frame = ttk.Frame(window, padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=message, justify="center").pack()
        self._bar = ttk.Progressbar(frame, mode="indeterminate", length=300)
        self._bar.pack(pady=(18, 0))
        self._bar.start(12)
        if modal:
            window.transient(parent)
        self._center()
        if modal:
            # A grab timeout raises out of __init__, so _run_with_wait never
            # receives the object and its `finally` cannot call close(). The
            # Toplevel would be left registered under the root with its
            # progress bar running and its close protocol a no-op -- an
            # unclosable stale window, and a fresh one accumulating on every
            # retry, because production calls originate in Tk callbacks where
            # an exception is reported without stopping the main loop. Tear
            # the partial window down before re-raising. Codex found this on
            # #221.
            try:
                self._take_grab()
            except Exception:
                try:
                    self._bar.stop()
                    window.destroy()
                except tk.TclError:
                    pass
                raise
        window.update()

    def _center(self) -> None:
        window = self._window
        window.update_idletasks()
        size = (window.winfo_width(), window.winfo_height())
        parent = self._parent
        rect = None
        if parent is not None and parent.winfo_viewable():
            rect = (
                parent.winfo_rootx(),
                parent.winfo_rooty(),
                parent.winfo_width(),
                parent.winfo_height(),
            )
        screen = (window.winfo_screenwidth(), window.winfo_screenheight())
        x, y = centered_origin(rect, size, screen)
        window.geometry(f"+{x}+{y}")

    def _take_grab(self) -> None:
        """Take the modal grab, retrying until the window is viewable.

        The grab is what blocks a second click on Apply while the first one is
        running. Tk refuses it with TclError until the window manager has made
        the window viewable, which is why the obvious `try/except: pass` looks
        harmless -- but swallowing the failure leaves every control underneath
        live. A double-click on Apply then gets through twice and starts two
        patch workers against the same output folder, which is precisely the
        thing the grab exists to prevent, and the window still looks modal.

        Waiting with `wait_visibility()` is not the fix: it blocks forever when
        the window never becomes viewable, which is exactly what a withdrawn or
        iconified parent produces. So this pumps the event loop and retries
        against a deadline, and raises if the grab never lands -- a visible
        failure at startup beats a modal window that is not modal.
        """
        deadline = time.monotonic() + GRAB_TIMEOUT_SECONDS
        while True:
            try:
                self._window.grab_set()
                return
            except tk.TclError:
                if time.monotonic() >= deadline:
                    raise
                # update_idletasks(), NOT update(). update() runs a nested
                # event loop that dispatches ARBITRARY pending events -- and
                # at this point no grab exists yet, so a click that arrived
                # during the retry window goes to the parent's Apply control
                # and re-enters _apply/_run_with_wait. That defeats the exact
                # modal guarantee this routine is here to provide. Idle tasks
                # cover the mapping and geometry work that makes the window
                # viewable, which is all the retry actually needs. Codex found
                # this on #221.
                try:
                    self._window.update_idletasks()
                except tk.TclError:
                    pass
                time.sleep(GRAB_POLL_SECONDS)

    def close(self) -> None:
        try:
            self._bar.stop()
            if self._modal:
                self._window.grab_release()
            self._window.destroy()
        except tk.TclError:
            pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Virtual Villagers Fun Patcher")
        self.geometry("940x760")
        self.minsize(820, 520)
        self.island_source = tk.PhotoImage(file=ROOT / "assets" / "Island.png")
        self.island_inline = self.island_source.subsample(
            max(1, round(self.island_source.width() / 22))
        )
        self.island_titlebar = self.island_source.subsample(
            max(1, round(self.island_source.width() / 32))
        )
        self.iconphoto(True, self.island_titlebar)
        # Hide the empty shell and put a splash up first: loading the patches
        # and building the chooser both happen before anything is drawn.
        self.withdraw()
        splash = WaitWindow(
            self,
            "Virtual Villagers Fun Patcher",
            "Please wait\u2026\n\nLoading the patches.",
            modal=False,
        )
        try:
            self.builds = load_builds()
            self.patch_modes = load_patch_modes()
            self.fun_patches = load_public_fun_patches()
            # Every fun patch starts selected. The owner's standing rule is
            # that a build never silently lacks a feature, so the default is
            # everything on and unticking is the deliberate act.
            #
            # Not driven by data/builds.json's `default_selected`: nothing in
            # src/ or scripts/ reads that field, so it decides nothing and
            # setting it would leave every box unticked exactly as before.
            #
            # Safe as a blanket default because no fun patch declares a
            # conflict. The only declared relationships are dependencies --
            # each game's village-wide upgrades, and VV2's parentage log,
            # require that game's Origins base -- and selecting everything
            # satisfies those by construction.
            self.fun_patch_vars = {
                patch.id: tk.BooleanVar(
                    value=default_fun_patch_selection(patch.id)
                )
                for patch in self.fun_patches
            }
            self._last_fun_selection: set[str] = set()
            self.exe_var = tk.StringVar()
            self.patch_mode_var = tk.StringVar(value=DEFAULT_PATCH_MODE)
            self.output_root_var = tk.StringVar()
            # "Check logs automatically": OFF by default (owner, 2026-10-05);
            # a per-install choice, written into each game built from now on.
            self.check_logs_var = tk.BooleanVar(value=False)
            self.all_folder_vars = {build.id: tk.StringVar() for build in self.builds}
            self.status_var = tk.StringVar(
                value="Choose a population mode and one game or all five."
            )
            self.game_var = tk.StringVar(value="No game identified yet")
            self.last_output_dir: Path | None = None
            self.last_modified_paths: dict[str, Path] = {}
            self._load_settings()
            # Record the starting selection as the baseline the dependency
            # closure diffs against. _load_settings does this only when a
            # saved selection exists; on a fresh install the baseline stayed
            # empty, so the first untick of a prerequisite read every ticked
            # patch as newly added and ticked the prerequisite straight back.
            self._apply_gui_dependency_selection()
            self._build_ui()
            self._mode_changed(save=False)
        finally:
            splash.close()
            self.deiconify()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _run_with_wait(self, message: str, work):
        """Run ``work`` off the main thread while a wait window stays alive.

        ``work`` must not touch Tk.  Every caller therefore reads its Tk
        variables on the main thread and closes over plain values, because
        reading a Tk variable from another thread is not safe.

        Pumping the event loop here is what keeps the window painting and the
        progress bar moving, which is the whole point: the same call made
        directly would leave the patcher looking hung for its whole duration.
        """
        wait = WaitWindow(self, "Please wait", message)
        # The wait window's own close is disabled, but that does nothing for the
        # ROOT window: while this pumps the event loop, closing the app from its
        # title bar or the taskbar would run App._close, destroy every widget,
        # and leave the worker running against a dead UI. Suppress the root's
        # close handler for the duration and restore it afterwards.
        previous_close = self.protocol("WM_DELETE_WINDOW")
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        outcome: dict = {}

        def run() -> None:
            try:
                outcome["value"] = work()
            except BaseException as exc:  # re-raised on the main thread below
                outcome["error"] = exc

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            while worker.is_alive():
                self.update()
                time.sleep(WAIT_POLL_SECONDS)
            worker.join()
        finally:
            wait.close()
            self.protocol("WM_DELETE_WINDOW", self._close)
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def _build_ui(self) -> None:
        viewport = ttk.Frame(self)
        viewport.pack(fill="both", expand=True)
        style = ttk.Style(self)
        self.content_canvas = tk.Canvas(
            viewport,
            background=style.lookup("TFrame", "background"),
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)

        outer = ttk.Frame(self.content_canvas, padding=18)
        self.content_window = self.content_canvas.create_window(
            (0, 0),
            window=outer,
            anchor="nw",
        )
        outer.bind("<Configure>", self._content_resized)
        self.content_canvas.bind("<Configure>", self._viewport_resized)
        self.bind_all("<MouseWheel>", self._scroll_content)

        title_row = ttk.Frame(outer)
        title_row.pack(anchor="w")
        ttk.Label(
            title_row,
            image=self.island_inline,
        ).pack(side="left", padx=(0, 6))
        ttk.Label(
            title_row,
            text="Virtual Villagers Fun Patcher",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")
        ttk.Label(
            title_row,
            image=self.island_inline,
        ).pack(side="left", padx=(6, 0))
        credit_row = ttk.Frame(outer)
        credit_row.pack(anchor="w", pady=(2, 4))
        ttk.Label(credit_row, image=self.island_inline).pack(side="left", padx=(0, 4))
        ttk.Label(
            credit_row,
            text="Created with Codex AI. Made with love by Lorsieab2 :)",
        ).pack(side="left")
        ttk.Label(credit_row, image=self.island_inline).pack(side="left", padx=(4, 0))
        proofread_row = ttk.Frame(outer)
        proofread_row.pack(anchor="w", pady=(0, 4))
        ttk.Label(
            proofread_row,
            text="Proofread by Claude AI",
        ).pack(side="left")
        blurb_row = ttk.Frame(outer)
        blurb_row.pack(fill="x", pady=(0, 10))
        # The link is packed FIRST so it keeps its full width and the
        # description takes whatever is left; packing it second would let a
        # long description squeeze it off the edge on a narrow window.
        update_box = ttk.Frame(blurb_row)
        update_box.pack(side="right", anchor="ne", padx=(12, 0))
        ttk.Label(update_box, text=PATCHER_VERSION).pack(anchor="e")
        self._folder_link(
            update_box, "Check for updates", self._open_releases_page
        ).pack(anchor="e", pady=(2, 0))
        ttk.Label(
            blurb_row,
            text="Creates a verified complete copy of each game folder and adds the modified EXE there. Originals are never replaced.",
            wraplength=700,
            justify="left",
        ).pack(side="left", anchor="nw")
        ttk.Label(
            outer,
            text=(
                "VV5 population safety: unconverted Heathens already occupy villager slots. "
                "Births reserve room for them; converting a Heathen reuses that same record "
                "and can still occur when every physical slot is occupied."
            ),
            wraplength=880,
            foreground="#8a4b08",
        ).pack(anchor="w", pady=(0, 10))

        mode_box = ttk.LabelFrame(outer, text="Population mode", padding=10)
        mode_box.pack(fill="x", pady=(0, 10))
        for row, mode in enumerate(self.patch_modes):
            ttk.Radiobutton(
                mode_box,
                text=mode.name,
                value=mode.id,
                variable=self.patch_mode_var,
                command=self._mode_changed,
            ).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=3)
            ttk.Label(mode_box, text=mode.description, wraplength=650).grid(
                row=row, column=1, sticky="w", pady=3
            )
        self.mode_detail_var = tk.StringVar()
        ttk.Label(
            mode_box,
            textvariable=self.mode_detail_var,
            wraplength=850,
            foreground="#245a9a",
        ).grid(row=len(self.patch_modes), column=0, columnspan=2, sticky="w", pady=(7, 0))
        fun_row = len(self.patch_modes) + 1
        ttk.Separator(mode_box).grid(row=fun_row, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(mode_box, text="Additional fun patches").grid(row=fun_row + 1, column=0, sticky="nw", pady=3)
        fun_actions = ttk.Frame(mode_box)
        fun_actions.grid(row=fun_row + 1, column=1, sticky="w", pady=(0, 5))
        ttk.Button(
            fun_actions,
            text="Select All Patches",
            command=self._select_all_fun_patches,
        ).pack(side="left")
        ttk.Button(
            fun_actions,
            text="Default Patches",
            command=self._default_fun_patches,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            fun_actions,
            text="Owner's Defaults",
            command=self._owners_default_fun_patches,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            fun_actions,
            text="Deselect All Patches",
            command=self._deselect_all_fun_patches,
        ).pack(side="left", padx=(8, 0))
        # The owner's rule: under every description, in bold, which other
        # patches must be on for this one (and which need this one).
        requirement_font = tkfont.nametofont("TkDefaultFont").copy()
        requirement_font.configure(weight="bold")
        description_font = tkfont.nametofont("TkDefaultFont")
        description_background = ttk.Style().lookup("TLabelframe", "background") or self.cget("background")
        row = fun_row + 2
        for header, patches in group_fun_patches(self.builds, self.fun_patches):
            if header == "Shared / All Games":
                ttk.Label(
                    mode_box,
                    text=header,
                    font=("Segoe UI", 10, "bold"),
                ).grid(row=row, column=1, sticky="w", pady=(8, 2))
                row += 1
                for patch in patches:
                    ttk.Checkbutton(
                        mode_box,
                        text=patch.name,
                        variable=self.fun_patch_vars[patch.id],
                        command=self._fun_patch_changed,
                    ).grid(row=row, column=1, sticky="w", pady=3)
                    row += 1
                    RichDescription(mode_box, patch.description, 620, requirement_font,
                                    description_font, description_background).grid(
                        row=row, column=1, sticky="w", pady=(0, 3)
                    )
                    row += 1
                    ttk.Label(
                        mode_box,
                        text=patch_requirement_text(patch, self.fun_patches),
                        wraplength=620,
                        font=requirement_font,
                    ).grid(row=row, column=1, sticky="w", pady=(0, 6))
                    row += 1
                continue
            ttk.Label(
                mode_box,
                text=header,
                font=("Segoe UI", 10, "bold"),
            ).grid(row=row, column=1, sticky="w", pady=(8, 2))
            row += 1
            for patch in patches:
                game_name = header.removeprefix("Virtual Villagers - ")
                ttk.Checkbutton(
                    mode_box,
                    text=f"{patch.name} ({game_name})",
                    variable=self.fun_patch_vars[patch.id],
                    command=self._fun_patch_changed,
                ).grid(row=row, column=1, sticky="w", pady=3)
                row += 1
                RichDescription(mode_box, patch.description, 620, requirement_font,
                                description_font, description_background).grid(
                    row=row, column=1, sticky="w", pady=(0, 3)
                )
                row += 1
                ttk.Label(
                    mode_box,
                    text=patch_requirement_text(patch, self.fun_patches),
                    wraplength=620,
                    font=requirement_font,
                ).grid(row=row, column=1, sticky="w", pady=(0, 6))
                row += 1
        mode_box.columnconfigure(1, weight=1)

        output_box = ttk.LabelFrame(outer, text="Modded output location", padding=10)
        output_box.pack(fill="x", pady=(0, 10))
        ttk.Entry(output_box, textvariable=self.output_root_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            output_box,
            text="Choose Folder...",
            command=self._browse_output_root,
        ).grid(row=0, column=1)
        ttk.Label(
            output_box,
            text=(
                "Choose the parent folder for the generated copies. Each result is written "
                "inside it as '(Game name) - Modded'. Leave blank to place each copy beside "
                "its supplied original folder."
            ),
            wraplength=850,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        output_box.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        single_tab = ttk.Frame(notebook, padding=14)
        all_tab = ttk.Frame(notebook, padding=14)
        notebook.add(single_tab, text="One Game")
        notebook.add(all_tab, text="All 5 Games")
        self._build_single_tab(single_tab)
        self._build_all_tab(all_tab)

        status_box = ttk.LabelFrame(outer, text="Status", padding=10)
        status_box.pack(fill="x", pady=(10, 0))
        ttk.Label(
            status_box,
            textvariable=self.status_var,
            wraplength=870,
            justify="left",
        ).pack(anchor="w")
        self.open_button = ttk.Button(
            status_box,
            text="Open Game Folder",
            command=self._open_output,
            state="disabled",
        )
        self.open_button.pack(anchor="e", pady=(8, 0))

    def _open_releases_page(self) -> None:
        """Open the project's GitHub page. No version check, by design.

        This used to ask GitHub for the newest tag and compare it against the
        build, which meant version parsing, prerelease ordering, a request
        timeout and a failure path for every way a network call can fail. The
        repository page already shows the latest release, and the build version is
        printed directly under this link, so the comparison is the player's to
        make and nothing here can hang or fail.
        """
        self.status_var.set(f"Opening {RELEASES_PAGE}")
        try:
            webbrowser.open(RELEASES_PAGE)
        except Exception as exc:                      # noqa: BLE001
            self.status_var.set(f"Could not open update link: {exc}")

    def _content_resized(self, _event: tk.Event) -> None:
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _viewport_resized(self, event: tk.Event) -> None:
        self.content_canvas.itemconfigure(self.content_window, width=event.width)

    def _scroll_content(self, event: tk.Event) -> str | None:
        bounds = self.content_canvas.bbox("all")
        if not bounds or bounds[3] <= self.content_canvas.winfo_height():
            return None
        direction = -1 if event.delta > 0 else 1
        self.content_canvas.yview_scroll(direction, "units")
        return "break"

    def _build_single_tab(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Original game executable", padding=10)
        box.pack(fill="x")
        ttk.Entry(box, textvariable=self.exe_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(box, text="Browse...", command=self._browse_exe).grid(row=0, column=1)
        box.columnconfigure(0, weight=1)
        ttk.Label(box, textvariable=self.game_var, foreground="#245a9a").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        links = ttk.Frame(box)
        links.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._folder_link(
            links, "Open Vanilla EXE Folder", self._open_single_vanilla_folder
        ).pack(side="left")
        self._folder_link(
            links, "Open Modified EXE Folder", self._open_single_modified_folder
        ).pack(side="left", padx=(18, 0))
        self._folder_link(
            links, "Back Up Saves", self._back_up_single_saves
        ).pack(side="left", padx=(18, 0))
        self._folder_link(
            links, "Restore Saves...", self._restore_single_saves
        ).pack(side="left", padx=(18, 0))
        self._folder_link(
            links, "Rename Tribe...", self._rename_single_tribe
        ).pack(side="left", padx=(18, 0))
        self._folder_link(
            links, "Check Logs...", self._check_single_logs
        ).pack(side="left", padx=(18, 0))
        self._folder_link(
            links, "Repair Logs...", self._repair_single_logs
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            box,
            text=CHECK_LOGS_LABEL,
            variable=self.check_logs_var,
            command=self._check_logs_changed,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(
            tab,
            text="Near the slot ceiling, multiple births and population-adding Island Events are safely reduced or blocked to fit the remaining physical slots.",
            wraplength=840,
        ).pack(anchor="w", pady=12)
        actions = ttk.Frame(tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Validate", command=self._validate).pack(side="left")
        ttk.Button(actions, text="Dry Run", command=self._dry_run).pack(side="left", padx=8)
        ttk.Button(actions, text="Create Modified EXE", command=self._apply).pack(side="left")

    def _build_all_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(
            tab,
            text="Choose one game folder per row. Each result is a complete copy containing all original files plus the modified EXE. Use the output location above to choose where the copies go.",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 8))
        grid = ttk.Frame(tab)
        grid.pack(fill="both", expand=True)
        for row, build in enumerate(self.builds):
            short = build.title.removeprefix("Virtual Villagers - ")
            ttk.Label(
                grid,
                text=f"{row + 1}. {short} ({build.villager_slots} stock slots)",
            ).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(grid, textvariable=self.all_folder_vars[build.id]).grid(
                row=row, column=1, sticky="ew", padx=(0, 8), pady=4
            )
            ttk.Button(
                grid,
                text="Choose Folder...",
                command=lambda game_id=build.id: self._browse_bulk_folder(game_id),
            ).grid(row=row, column=2, pady=4)
            self._folder_link(
                grid,
                "Vanilla folder",
                lambda game_id=build.id: self._open_bulk_folder(game_id, False),
            ).grid(row=row, column=3, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Modified folder",
                lambda game_id=build.id: self._open_bulk_folder(game_id, True),
            ).grid(row=row, column=4, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Back up saves",
                lambda game=build: self._back_up_saves([game]),
            ).grid(row=row, column=5, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Restore saves...",
                lambda game=build: self._restore_saves(game),
            ).grid(row=row, column=6, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Rename tribe...",
                lambda game=build: self._rename_tribe(game),
            ).grid(row=row, column=7, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Check logs...",
                lambda game=build: self._log_tool(game, repair=False),
            ).grid(row=row, column=8, padx=(12, 0), pady=4)
            self._folder_link(
                grid,
                "Repair logs...",
                lambda game=build: self._log_tool(game, repair=True),
            ).grid(row=row, column=9, padx=(12, 0), pady=4)
        grid.columnconfigure(1, weight=1)
        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="Find All 5 in Parent Folder...",
            command=self._find_all,
        ).pack(side="left")
        ttk.Button(
            actions, text="Validate All 5", command=self._validate_all
        ).pack(side="left", padx=(16, 8))
        ttk.Button(
            actions, text="Dry Run All 5", command=self._dry_run_all
        ).pack(side="left")
        ttk.Button(
            actions, text="Patch All 5", command=self._apply_all
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Back Up Saves (All 5)...",
            command=lambda: self._back_up_saves(list(self.builds)),
        ).pack(side="left", padx=(16, 0))
        ttk.Button(
            actions,
            text="Rename Tribe...",
            command=lambda: self._rename_tribe(None),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Check Logs...",
            command=lambda: self._log_tool(None, repair=False),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Repair Logs...",
            command=lambda: self._log_tool(None, repair=True),
        ).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            tab,
            text=CHECK_LOGS_LABEL,
            variable=self.check_logs_var,
            command=self._check_logs_changed,
        ).pack(anchor="w", pady=(8, 0))

    def _mode(self) -> str:
        return self.patch_mode_var.get()

    def _check_logs_changed(self) -> None:
        """The "Check logs automatically" box: remembered, and used for every
        game created from now on (a game already created keeps its own)."""
        if self.check_logs_var.get():
            self.status_var.set(
                "Check logs automatically: on. Games you create from now on check "
                "each village's logs silently while it is played and, only if "
                "something is wrong, ask Repair / Not now when you close the game."
            )
        else:
            self.status_var.set(
                "Check logs automatically: off. Games you create from now on never "
                "check or ask during play; use Check Logs and Repair Logs."
            )
        self._save_settings()

    def _mode_changed(self, save: bool = True) -> None:
        try:
            mode = get_patch_mode(self._mode())
        except PatcherError:
            self.patch_mode_var.set(DEFAULT_PATCH_MODE)
            mode = get_patch_mode(DEFAULT_PATCH_MODE)
        detail = mode.description
        self.mode_detail_var.set(detail)
        self.status_var.set(f"Selected: {mode.name}. {detail}")
        if save:
            self._save_settings()

    def _selected_fun_patch_ids(self, game_id: str | None = None) -> list[str]:
        selected = [
            patch.id
            for patch in self.fun_patches
            if self.fun_patch_vars[patch.id].get()
            and (game_id is None or patch.game_id == game_id)
        ]
        self._selection_error = None
        try:
            return resolve_fun_patch_ids(selected, game_id=game_id)
        except PatcherError as exc:
            # Keep settings and mode changes usable while an incompatible
            # checkbox combination is selected; patch/dry-run still rejects it
            # through the strict resolver with the actionable conflict text.
            self._selection_error = str(exc)
            return selected

    def _patch_dependency_map(self) -> dict[str, tuple[str, ...]]:
        dependencies: dict[str, tuple[str, ...]] = {}
        for patch in self.fun_patches:
            raw = patch.raw.get("dependencies", ())
            if isinstance(raw, str):
                raw = (raw,)
            dependencies[patch.id] = tuple(raw or ())
        return dependencies

    def _apply_gui_dependency_selection(self) -> None:
        """Keep checkbox state closed over prerequisites and dependent removals."""
        current = {
            patch.id
            for patch in self.fun_patches
            if self.fun_patch_vars[patch.id].get()
        }
        previous = set(self._last_fun_selection)
        dependencies = self._patch_dependency_map()
        by_id = {patch.id: patch for patch in self.fun_patches}

        # Checking a dependent automatically checks every prerequisite.
        added = current - previous
        pending = list(added)
        while pending:
            patch_id = pending.pop()
            for dependency_id in dependencies.get(patch_id, ()):
                if dependency_id not in by_id:
                    continue
                if dependency_id not in current:
                    current.add(dependency_id)
                    pending.append(dependency_id)

        # Unchecking a prerequisite clears every selected dependent below it.
        removed = previous - current
        pending = list(removed)
        while pending:
            prerequisite_id = pending.pop()
            for patch_id, required in dependencies.items():
                if prerequisite_id in required and patch_id in current:
                    current.remove(patch_id)
                    pending.append(patch_id)

        for patch in self.fun_patches:
            self.fun_patch_vars[patch.id].set(patch.id in current)
        self._last_fun_selection = current

    def _fun_patch_changed(self) -> None:
        self._apply_gui_dependency_selection()
        self._selected_fun_patch_ids()
        selected = [
            patch.name
            for patch in self.fun_patches
            if self.fun_patch_vars[patch.id].get()
        ]
        if self._selection_error:
            self.status_var.set("Selection error: " + self._selection_error)
        else:
            self.status_var.set(
                "Additional patches: " + (", ".join(selected) if selected else "none")
            )
        self._save_settings()

    def _select_all_fun_patches(self) -> None:
        for patch_id, variable in self.fun_patch_vars.items():
            variable.set(select_all_fun_patch_selection(patch_id))
        self._last_fun_selection = set()
        self._fun_patch_changed()

    def _default_fun_patches(self) -> None:
        """Restore the default selection: everything except the deny-list.

        Distinct from Select All, which ticks everything except 256 Villagers
        (Experimental). This is
        the selection a fresh install starts with, so a player who has been
        experimenting can get back to it without knowing which patches the
        default holds back.
        """
        for patch_id, variable in self.fun_patch_vars.items():
            variable.set(default_fun_patch_selection(patch_id))
        self._last_fun_selection = set()
        self._fun_patch_changed()

    def _owners_default_fun_patches(self) -> None:
        """The owner's own selection: every patch except Learning Skills
        Never Fails, including the other default-off patches."""
        for patch_id, variable in self.fun_patch_vars.items():
            variable.set(owners_default_fun_patch_selection(patch_id))
        self._last_fun_selection = set()
        self._fun_patch_changed()

    def _deselect_all_fun_patches(self) -> None:
        for variable in self.fun_patch_vars.values():
            variable.set(False)
        self._last_fun_selection = set()
        self._fun_patch_changed()

    def _load_settings(self) -> None:
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        saved_mode = data.get("patch_mode", DEFAULT_PATCH_MODE)
        if saved_mode in {mode.id for mode in self.patch_modes}:
            self.patch_mode_var.set(saved_mode)
        # Only an actually-present saved selection may override the
        # all-selected default. Reading a missing key as an empty list would
        # turn every patch off on a fresh install -- where the settings file
        # does not exist and data is {} -- and on any older settings file
        # written before this key existed, which is precisely when the
        # default is supposed to apply.
        selected_fun = data.get("fun_patches")
        if isinstance(selected_fun, list):
            for patch in self.fun_patches:
                self.fun_patch_vars[patch.id].set(patch.id in selected_fun)
            self._last_fun_selection = set()
            self._apply_gui_dependency_selection()
        self.exe_var.set(data.get("original_exe", ""))
        saved_output_root = data.get("output_root", "")
        if isinstance(saved_output_root, str):
            self.output_root_var.set(saved_output_root)
        saved_check_logs = data.get("check_logs_automatically", False)
        self.check_logs_var.set(saved_check_logs is True)
        saved_all = data.get("all_game_folders", data.get("all_game_exes", {}))
        if isinstance(saved_all, dict):
            for build in self.builds:
                value = saved_all.get(build.id, "")
                if isinstance(value, str):
                    path = Path(value)
                    if path.name.casefold() == build.input_name.casefold():
                        value = str(path.parent)
                    self.all_folder_vars[build.id].set(value)

    def _save_settings(self) -> None:
        data = {
            "patch_mode": self._mode(),
            "original_exe": self.exe_var.get().strip(),
            "output_root": self.output_root_var.get().strip(),
            "check_logs_automatically": bool(self.check_logs_var.get()),
            "fun_patches": self._selected_fun_patch_ids(),
            "all_game_folders": {
                build.id: self.all_folder_vars[build.id].get().strip()
                for build in self.builds
            },
        }
        SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _browse_exe(self) -> None:
        current = Path(self.exe_var.get()).parent if self.exe_var.get() else Path.home()
        chosen = filedialog.askopenfilename(
            title="Choose the original Virtual Villagers EXE",
            initialdir=current,
            filetypes=[("Windows executables", "*.exe"), ("All files", "*.*")],
        )
        if chosen:
            self.exe_var.set(chosen)
            self._save_settings()
            self._validate(show_popup=False)

    def _browse_output_root(self) -> None:
        current = Path(self.output_root_var.get()) if self.output_root_var.get() else Path.home()
        if not current.is_dir():
            current = Path.home()
        chosen = filedialog.askdirectory(
            title="Choose the parent folder for modded game folders",
            initialdir=current,
        )
        if chosen:
            self.output_root_var.set(chosen)
            self._save_settings()
            self.status_var.set(
                f"Modded copies will be placed under: {Path(chosen).resolve()}"
            )

    def _browse_bulk_folder(self, game_id: str) -> None:
        variable = self.all_folder_vars[game_id]
        current = Path(variable.get()) if variable.get() else Path.home()
        build = next(item for item in self.builds if item.id == game_id)
        chosen = filedialog.askdirectory(
            title=f"Choose the folder containing {build.input_name}",
            initialdir=current,
        )
        if chosen:
            variable.set(chosen)
            self._save_settings()

    def _find_all(self) -> None:
        chosen = filedialog.askdirectory(
            title="Choose the parent folder containing the five game folders",
            initialdir=Path.home(),
        )
        if not chosen:
            return
        root = Path(chosen)
        try:
            children = [path for path in root.iterdir() if path.is_dir()]
        except OSError as exc:
            messagebox.showerror("Cannot search folder", str(exc))
            return
        problems = []
        found = 0
        for build in self.builds:
            candidates = [root / build.input_name]
            candidates.extend(child / build.input_name for child in children)
            matches = [path for path in candidates if path.is_file()]
            if len(matches) == 1:
                self.all_folder_vars[build.id].set(str(matches[0].parent))
                found += 1
            elif not matches:
                problems.append(f"Not found: {build.input_name}")
            else:
                problems.append(f"More than one match: {build.input_name}")
        self._save_settings()
        self.status_var.set(
            f"Found {found} of 5 original EXEs."
            + ("\n" + "\n".join(problems) if problems else "")
        )
        if problems:
            messagebox.showwarning("Folder search finished", self.status_var.get())
        else:
            self._validate_all()

    def _source(self) -> Path:
        value = self.exe_var.get().strip()
        if not value:
            raise PatcherError("Choose an original game executable first.")
        return Path(value)

    def _output_root(self) -> Path | None:
        value = self.output_root_var.get().strip()
        return Path(value).expanduser() if value else None

    def _all_sources(self) -> dict[str, Path]:
        values = {
            build.id: self.all_folder_vars[build.id].get().strip()
            for build in self.builds
        }
        missing = [build.title for build in self.builds if not values[build.id]]
        if missing:
            raise PatcherError(
                "Choose all five original game folders. Missing: " + ", ".join(missing)
            )
        return {game_id: Path(value) for game_id, value in values.items()}

    def _selection_text(self, build=None) -> str:
        mode = get_patch_mode(self._mode())
        prefix = f"{build.title}: " if build else ""
        if mode.id == "stock":
            text = (
                "the stock population cap and progression behavior are preserved; "
                "automatic physical-capacity safety still clamps allocation paths."
            )
        elif mode.id == "collection_progression":
            text = "collection bonuses remain active and are needed for the absolute maximum."
        elif mode.id == "immediate_fixed":
            text = "the absolute maximum is immediate; collection bonuses do not affect it."
        else:
            text = "collection bonuses remain active and are needed for the absolute maximum."
        selected = self._selected_fun_patch_ids(build.id if build else None)
        if selected:
            names = [patch.name for patch in self.fun_patches if patch.id in selected]
            text += " Additional: " + ", ".join(names) + "."
        return prefix + text

    def _validate(self, show_popup: bool = True) -> None:
        try:
            build = identify(self._source())
            variant = get_patch_variant(build, self._mode())
            maximum = variant.get("absolute_maximum", build.absolute_maximum)
            self.game_var.set(
                f"Supported build: {build.title} - selected mode maximum {maximum}"
            )
            self.status_var.set(f"Validated. {self._selection_text(build)}")
            self._save_settings()
            if show_popup:
                messagebox.showinfo("Validated", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.game_var.set("Unsupported or unrecognized executable")
            self.status_var.set(str(exc))
            if show_popup:
                messagebox.showerror("Cannot validate", str(exc))

    def _validate_all(self) -> None:
        try:
            sources = self._all_sources()   # Tk read stays on the main thread
            validated = self._run_with_wait(
                "Please wait\u2026\n\nChecking all five original games.",
                lambda: validate_all_sources(sources),
            )
            self.status_var.set(
                "All five exact stock builds validated. "
                + self._selection_text()
                + "\n"
                + "\n".join(f"- {build.title}" for build, _ in validated)
            )
            self._save_settings()
            messagebox.showinfo("All five validated", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Cannot validate all five", str(exc))

    def _dry_run(self) -> None:
        try:
            source = self._source()
            build = identify(source)
            # Tk reads on the main thread; the worker gets plain values.
            mode = self._mode()
            fun_patch_ids = self._selected_fun_patch_ids(build.id)
            output_root = self._output_root()
            check_logs = bool(self.check_logs_var.get())
            result = self._run_with_wait(
                f"Please wait\u2026\n\nChecking {build.title}\nand preparing its patches.",
                lambda: dry_run(
                    source, mode, fun_patch_ids, output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            self.status_var.set(
                "Dry run passed. No files were written. Planned copied game folder:\n"
                + result["output_folder"]
                + "\nModified EXE:\n"
                + result["output_path"]
                + "\n"
                + self._selection_text()
                + "\nMultiple births and Island Event arrivals safely fit the remaining physical slots.\nExpected SHA-256: "
                + result["result_sha256"]
            )
            self._save_settings()
            messagebox.showinfo("Dry run passed", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Dry run failed", str(exc))

    def _dry_run_all(self) -> None:
        try:
            sources = self._all_sources()
            mode = self._mode()
            fun_patch_ids = self._selected_fun_patch_ids()
            output_root = self._output_root()
            check_logs = bool(self.check_logs_var.get())
            results = self._run_with_wait(
                "Please wait\u2026\n\nPreparing the patches for all five games.",
                lambda: dry_run_all(
                    sources, mode, fun_patch_ids, output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            self.status_var.set(
                "All-five dry run passed. No files were written. "
                + self._selection_text()
                + "\n"
                + "\n".join(f"- {result['output_folder']}" for result in results)
            )
            self._save_settings()
            messagebox.showinfo("All-five dry run passed", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("All-five dry run failed", str(exc))

    def _confirm_unmet_needs_on(self, fun_patch_ids: list[str]) -> bool:
        """Tell the player about co-required patches that are off, then ask.

        The owner's rule is confirm, not hard-block: the patch runs if they
        say yes.  Returns True when patching should go ahead.
        """
        try:
            body = unmet_needs_on_text(fun_patch_ids, self.fun_patches)
        except PatcherError:
            # A malformed needs_on is the strict resolver's to report, with
            # its actionable text; it must not silently block patching here.
            return True
        if not body:
            return True
        return messagebox.askyesno("A patch this one works with is off", body)

    def _apply(self) -> None:
        try:
            _validate_public_patch_mode(self._mode())
            source = self._source()
            build = identify(source)
            # Read every Tk variable here; the worker thread must not.
            mode = self._mode()
            fun_patch_ids = self._selected_fun_patch_ids(build.id)
            if not self._confirm_unmet_needs_on(fun_patch_ids):
                return
            output_root = self._output_root()
            check_logs = bool(self.check_logs_var.get())
            preview = self._run_with_wait(
                f"Please wait\u2026\n\nChecking {build.title}\nand preparing its patches.",
                lambda: dry_run(
                    source, mode, fun_patch_ids, output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            output_folder = Path(preview["output_folder"])
            overwrite = False
            if output_folder.exists():
                overwrite = messagebox.askyesno(
                    "Replace existing copied game folder?",
                    f"This complete copied game folder already exists:\n\n{output_folder}\n\nReplace the whole copied folder with a newly verified copy of the selected original?",
                )
                if not overwrite:
                    return
            output, log = self._run_with_wait(
                f"Please wait\u2026\n\nCopying and patching {build.title}.\n\n"
                "Copying the whole game folder can take a while.",
                lambda: apply_patch(
                    source,
                    mode,
                    overwrite=overwrite,
                    fun_patch_ids=fun_patch_ids,
                    output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            self.last_output_dir = output.parent
            self.last_modified_paths[build.id] = output
            self.open_button.configure(text="Open Game Folder", state="normal")
            self.status_var.set(
                f"Success. Created {output.name} in {output.parent.name}."
            )
            self._save_settings()
            self._show_folder_confirmation(
                "Modified game created",
                [(build.title, source.parent, output.parent)],
            )
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Patch failed", str(exc))

    def _apply_all(self) -> None:
        try:
            _validate_public_patch_mode(self._mode())
            sources = self._all_sources()
            # Read every Tk variable here; the worker thread must not.
            mode = self._mode()
            fun_patch_ids = self._selected_fun_patch_ids()
            if not self._confirm_unmet_needs_on(fun_patch_ids):
                return
            output_root = self._output_root()
            check_logs = bool(self.check_logs_var.get())
            validated = self._run_with_wait(
                "Please wait\u2026\n\nChecking all five original games.",
                lambda: validate_all_sources(sources),
            )
            previews = self._run_with_wait(
                "Please wait\u2026\n\nPreparing the patches for all five games.",
                lambda: dry_run_all(
                    sources, mode, fun_patch_ids, output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            existing = []
            for (build, source), preview in zip(validated, previews, strict=True):
                output_folder = Path(preview["output_folder"])
                if output_folder.exists():
                    existing.append(output_folder)
            overwrite = False
            if existing:
                overwrite = messagebox.askyesno(
                    "Replace existing copied game folders?",
                    "One or more complete copied game folders already exist:\n\n"
                    + "\n".join(str(path) for path in existing)
                    + "\n\nReplace those copied folders with newly verified complete copies?",
                )
                if not overwrite:
                    return
            results = self._run_with_wait(
                "Please wait\u2026\n\nCopying and patching all five games.\n\n"
                "Copying five whole game folders can take several minutes.",
                lambda: apply_all(
                    sources,
                    mode,
                    overwrite=overwrite,
                    fun_patch_ids=fun_patch_ids,
                    output_root=output_root,
                    check_logs_automatically=check_logs,
                ),
            )
            self.last_output_dir = results[0][0].parent
            self.last_modified_paths = {
                build.id: output
                for (build, _), (output, _) in zip(validated, results, strict=True)
            }
            self.open_button.configure(text="Open First Game Folder", state="normal")
            self.status_var.set("Success. Created all five modified game folders.")
            self._save_settings()
            self._show_folder_confirmation(
                "All five modified games created",
                [
                    (build.title, source.parent, output.parent)
                    for (build, source), (output, _) in zip(validated, results, strict=True)
                ],
            )
        except (PatcherError, OSError, ValueError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Batch patch failed", str(exc))

    def _show_folder_confirmation(
        self,
        title: str,
        rows: list[tuple[str, Path, Path]],
    ) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(True, True)
        dialog.minsize(760, 480)
        dialog_width = min(1040, max(760, dialog.winfo_screenwidth() - 80))
        dialog_height = min(720, max(480, dialog.winfo_screenheight() - 120))
        dialog.geometry(f"{dialog_width}x{dialog_height}")

        viewport = ttk.Frame(dialog)
        viewport.pack(fill="both", expand=True)
        confirmation_canvas = tk.Canvas(
            viewport,
            borderwidth=0,
            highlightthickness=0,
        )
        confirmation_scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=confirmation_canvas.yview,
        )
        confirmation_canvas.configure(yscrollcommand=confirmation_scrollbar.set)
        confirmation_scrollbar.pack(side="right", fill="y")
        confirmation_canvas.pack(side="left", fill="both", expand=True)

        frame = ttk.Frame(confirmation_canvas, padding=16)
        confirmation_window = confirmation_canvas.create_window(
            (0, 0),
            window=frame,
            anchor="nw",
        )
        frame.bind(
            "<Configure>",
            lambda _event: confirmation_canvas.configure(
                scrollregion=confirmation_canvas.bbox("all")
            ),
        )
        confirmation_canvas.bind(
            "<Configure>",
            lambda event: confirmation_canvas.itemconfigure(
                confirmation_window,
                width=event.width,
            ),
        )

        def scroll_confirmation(event: tk.Event) -> str:
            direction = -1 if event.delta > 0 else 1
            confirmation_canvas.yview_scroll(direction, "units")
            return "break"

        dialog.bind("<MouseWheel>", scroll_confirmation)
        ttk.Label(
            frame,
            text="Finished! Open either folder:",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        row_number = 1
        for game_name, vanilla_folder, modded_folder in rows:
            ttk.Label(frame, text=game_name).grid(
                row=row_number, column=0, columnspan=2, sticky="w", pady=(6, 1)
            )
            self._folder_link(
                frame,
                f"Open Vanilla Folder: {vanilla_folder.name}",
                lambda path=vanilla_folder: self._open_folder(path),
            ).grid(row=row_number + 1, column=0, sticky="w", padx=(14, 22))
            self._folder_link(
                frame,
                f"Open Modded Folder: {modded_folder.name}",
                lambda path=modded_folder: self._open_folder(path),
            ).grid(row=row_number + 1, column=1, sticky="w")
            build = next((item for item in self.builds if item.title == game_name), None)
            if build is not None:
                output_name = get_patch_variant(build, self._mode())["output_name"]
                output_exe = modded_folder / output_name
                artifact_lines = [
                    f"Patch audit: {output_exe.with_suffix('.patch-log.json')} — exact build hash, selected patches, and applied edits."
                ]
                artifact_lines.append(
                    f"Transparency Log: {modded_folder / 'VVFP Transparency Log.txt'}"
                )
                selected = set(self._selected_fun_patch_ids(build.id))
                # THE LOGS GO WITH THE SAVE, NOT WITH THE INSTALL. The
                # exporters resolve Documents\LDW\<exe basename>\ -- the
                # folder the game itself saves into -- so pointing at
                # modded_folder sent a player to a directory where these files
                # are never created. Found in review.
                save_folder = (
                    _documents_folder() / "LDW" / output_exe.stem
                    / "Virtual Villagers Fun Patcher Logs"
                )
                if f"{build.id}_write_village_statistics" in selected:
                    artifact_lines.append(
                        f"Village Statistics v2 - Save N.txt: {save_folder / 'Village Statistics'} — refreshed after each successful save; contains that save's lifetime statistics (the earlier 'Village Statistics - Save N.txt' is kept as it was)."
                    )
                if f"{build.id}_write_parentage_log" in selected:
                    # The game number comes from the build. The condition above
                    # is generic over every game, so a hardcoded "Virtual
                    # Villagers 1" sent a VV2 player looking for a file the
                    # companion never writes: each log is named after its own
                    # game.
                    artifact_lines.append(
                        f"Virtual Villagers {build.id.removeprefix('vv')} Births and Conceptions Log N.txt: "
                        f"{save_folder / 'Births and Conceptions'} — one plain-text record per pregnancy, written at "
                        "conception; rolls to a new numbered file every 256 records."
                    )
                ttk.Label(
                    frame,
                    text="\n".join(artifact_lines),
                    wraplength=830,
                    justify="left",
                    foreground="#5a4a36",
                ).grid(
                    row=row_number + 2,
                    column=0,
                    columnspan=2,
                    sticky="w",
                    padx=(14, 0),
                    pady=(2, 8),
                )
                row_number += 3
            else:
                row_number += 2

        ttk.Button(frame, text="Close", command=dialog.destroy).grid(
            row=row_number, column=0, columnspan=2, pady=(16, 0)
        )
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()
        dialog.focus_set()

    def _open_output(self) -> None:
        if self.last_output_dir is None:
            return
        self._open_folder(self.last_output_dir)

    def _folder_link(self, parent, text: str, command):
        """A clickable, underlined link label.

        The font is a COPY of TkDefaultFont with underline turned on, never a
        hardcoded family and size. Naming a point size here shrinks every link
        on any setup where TkDefaultFont has been enlarged for readability,
        while the labels around it stay large -- the opposite of making a link
        easy to see. The underline is what makes it read as a link at all:
        without it this is just differently coloured text sitting next to its
        neighbours, and gets reported as missing even while it is on screen and
        working.
        """
        link_font = tkfont.nametofont("TkDefaultFont").copy()
        link_font.configure(underline=True)
        link = tk.Label(
            parent,
            text=text,
            foreground=LINK_COLOR,
            cursor="hand2",
            font=link_font,
        )
        link.bind("<Button-1>", lambda _event: command())
        link.bind("<Enter>", lambda _event: link.configure(foreground=LINK_HOVER_COLOR))
        link.bind("<Leave>", lambda _event: link.configure(foreground=LINK_COLOR))
        return link

    def _open_folder(self, path: Path) -> None:
        target = path.expanduser()
        if target.is_file():
            target = target.parent
        if not target.is_dir():
            self.status_var.set(f"Folder not found: {target}")
            messagebox.showerror("Cannot open folder", self.status_var.get())
            return
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def _open_single_vanilla_folder(self) -> None:
        value = self.exe_var.get().strip()
        if not value:
            messagebox.showinfo("Choose a game", "Choose an original game EXE first.")
            return
        self._open_folder(Path(value))

    def _open_single_modified_folder(self) -> None:
        value = self.exe_var.get().strip()
        if not value:
            messagebox.showinfo("Choose a game", "Choose an original game EXE first.")
            return
        try:
            build = identify(Path(value))
            target = self.last_modified_paths.get(build.id)
            if target is None:
                preview = dry_run(
                    Path(value),
                    self._mode(),
                    self._selected_fun_patch_ids(build.id),
                    output_root=self._output_root(),
                )
                target = Path(preview["output_folder"])
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Cannot locate modified folder", str(exc))
            return
        self._open_folder(target)

    def _open_bulk_folder(self, game_id: str, modified: bool) -> None:
        value = self.all_folder_vars[game_id].get().strip()
        if not value:
            messagebox.showinfo("Choose a folder", "Choose this game's folder first.")
            return
        target = Path(value)
        if modified:
            target = self.last_modified_paths.get(game_id)
            if target is None:
                try:
                    build = next(build for build in self.builds if build.id == game_id)
                    source = Path(value)
                    if source.is_dir():
                        source = source / build.input_name
                    preview = dry_run(
                        source,
                        self._mode(),
                        self._selected_fun_patch_ids(game_id),
                        output_root=self._output_root(),
                    )
                    target = Path(preview["output_folder"])
                except (PatcherError, OSError) as exc:
                    self.status_var.set(str(exc))
                    messagebox.showerror("Cannot locate modified folder", str(exc))
                    return
        self._open_folder(target)

    # -- Back Up Saves ------------------------------------------------------

    def _back_up_single_saves(self) -> None:
        """Back Up Saves for the game chosen on the One Game tab."""
        build = self._single_build()
        if build is not None:
            self._back_up_saves([build])

    def _single_build(self):
        """The game chosen on the One Game tab, or None (after telling the player).

        The game is named by the chosen EXE's file name ("<title>.exe" or a
        built "<title> - Modded....exe"), which needs no hashing; only an exe
        renamed past recognition is identified by its contents.
        """
        value = self.exe_var.get().strip()
        if not value:
            messagebox.showinfo("Choose a game", "Choose an original game EXE first.")
            return None
        stem = Path(value).stem.casefold()
        build = next(
            (item for item in self.builds if stem.startswith(item.title.casefold())),
            None,
        )
        if build is None:
            try:
                build = identify(Path(value))
            except (PatcherError, OSError) as exc:
                messagebox.showerror("Cannot tell which game this is", str(exc))
                return None
        return build

    def _back_up_saves(self, builds) -> None:
        """Let the player pick save folders, then pause each game and copy.

        Lists every Documents\\LDW\\<title> - Modded... folder of the given
        games. The folders of games the patcher built are ticked; others (a
        copy the player made, say) are listed unticked.
        """
        documents = vv_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                "Back Up Saves",
                "Windows did not report where your Documents folder is, so the "
                "save folders cannot be found.",
            )
            return
        found = [
            (build, folder)
            for build in builds
            for folder in vv_save_backup.find_save_folders(build.title, documents)
        ]
        if not found:
            names = ", ".join(
                build.title.removeprefix("Virtual Villagers - ") for build in builds
            )
            messagebox.showinfo(
                "Back Up Saves",
                f"No modded save folders were found for {names} in "
                f"{documents / 'LDW'}.\n\nA modded game makes its save folder the "
                "first time it is played.",
            )
            return
        self._show_backup_chooser(found)

    def _scrolling_dialog(self, title: str):
        """A dialog whose content scrolls once it is taller than the screen.

        With All 5 games and several variants each, the chooser and the
        results can list twenty folders; unbounded, the last ones and the
        buttons would fall off the bottom of the screen.
        """
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        canvas = tk.Canvas(dialog, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame = ttk.Frame(canvas, padding=16)
        window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def fit(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            height = min(frame.winfo_reqheight(), dialog.winfo_screenheight() - 160)
            canvas.configure(width=frame.winfo_reqwidth(), height=height)

        frame.bind("<Configure>", fit)
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfigure(window, width=event.width)
        )
        dialog.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"),
        )
        return dialog, frame

    def _show_backup_chooser(self, found) -> None:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        ttk.Label(
            frame,
            text="Choose the save folders to back up:",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Each folder is copied into a new dated folder inside it: "
                "<save folder>\\Backups\\Backup <date and time>. "
                "If the game is running it is paused for the copy and then "
                "resumes by itself. These games save only when you quit "
                "normally, so a backup made while a game is running holds the "
                "village as of its last save."
            ),
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))
        choices: list[tuple[Path, tk.BooleanVar]] = []
        current = None
        for build, folder in found:
            if build is not current:
                current = build
                ttk.Label(frame, text=build.title).pack(anchor="w", pady=(6, 0))
            label = folder.name
            if vv_save_backup.running_game_count(folder):
                label += "   (running: will be paused for the copy)"
            var = tk.BooleanVar(
                value=vv_save_backup.is_patcher_save_folder(build.title, folder.name)
            )
            ttk.Checkbutton(frame, text=label, variable=var).pack(
                anchor="w", padx=(14, 0)
            )
            choices.append((folder, var))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))

        def start() -> None:
            chosen = [folder for folder, var in choices if var.get()]
            if not chosen:
                messagebox.showinfo(
                    "Back Up Saves", "Tick at least one save folder.", parent=dialog
                )
                return
            dialog.destroy()
            self._run_backups(chosen)

        ttk.Button(buttons, text="Back Up Selected", command=start).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(
            side="left", padx=(8, 0)
        )
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()
        dialog.focus_set()

    def _run_backups(self, folders: list[Path]) -> None:
        def work():
            outcomes = []
            for folder in folders:
                try:
                    outcomes.append(
                        (folder, vv_save_backup.back_up_save_folder(folder), None)
                    )
                except (vv_save_backup.BackupError, OSError) as exc:
                    outcomes.append((folder, None, str(exc)))
            return outcomes

        outcomes = self._run_with_wait(
            "Backing up saves…\n\nA running game is paused for the copy.",
            work,
        )
        made = sum(1 for _folder, result, _error in outcomes if result is not None)
        self.status_var.set(
            f"Back Up Saves: {made} of {len(outcomes)} save folder(s) backed up."
        )
        self._show_backup_results(outcomes)

    def _show_backup_results(self, outcomes) -> None:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        for folder, result, error in outcomes:
            ttk.Label(frame, text=folder.name, font=("Segoe UI", 10, "bold")).pack(
                anchor="w", pady=(8, 0)
            )
            if result is None:
                ttk.Label(
                    frame,
                    text=f"NOT backed up: {error}",
                    wraplength=640,
                    justify="left",
                    foreground="#a01010",
                ).pack(anchor="w", padx=(14, 0))
                continue
            lines = [
                f"Backed up {result.file_count} file(s), "
                f"{vv_save_backup.describe_size(result.total_bytes)}; every copy "
                "was checked against the original (size and SHA-256).",
                f"Backup folder: {result.backup_folder}",
            ]
            if result.paused:
                lines.append(
                    "The game was running: it was paused for the copy and has "
                    "resumed. The backup holds the village as of its last save "
                    "(the game saves when you quit it normally)."
                )
            else:
                lines.append("The game was not running.")
            ttk.Label(
                frame, text="\n".join(lines), wraplength=640, justify="left"
            ).pack(anchor="w", padx=(14, 0))
            if result.resume_problems:
                ttk.Label(
                    frame,
                    text=(
                        "The backup is complete, but the game could not be resumed: "
                        + "; ".join(result.resume_problems)
                        + ". If it stays frozen, close it from Task Manager; the "
                        "backup above is safe."
                    ),
                    wraplength=640,
                    justify="left",
                    foreground="#a01010",
                ).pack(anchor="w", padx=(14, 0))
            self._folder_link(
                frame,
                "Open Backup Folder",
                lambda path=result.backup_folder: self._open_folder(path),
            ).pack(anchor="w", padx=(14, 0), pady=(2, 0))
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=(16, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()
        dialog.focus_set()

    # -- Restore Saves -----------------------------------------------------

    def _restore_single_saves(self) -> None:
        build = self._single_build()
        if build is not None:
            self._restore_saves(build)

    def _restore_saves(self, build) -> None:
        """List this game's backups so the player can restore or delete one."""
        documents = vv_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                "Restore Saves",
                "Windows did not report where your Documents folder is, so the "
                "save folders cannot be found.",
            )
            return
        folders = vv_save_backup.find_save_folders(build.title, documents)
        if not any(vv_save_backup.list_backups(folder) for folder in folders):
            messagebox.showinfo(
                "Restore Saves",
                f"There are no backups of {build.title} yet.\n\nUse Back Up Saves "
                "to make one.",
            )
            return
        self._show_restore_window(build, folders)

    def _show_restore_window(self, build, folders) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"Restore Saves - {build.title.removeprefix('Virtual Villagers - ')}")
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame, text="Choose a backup to restore:", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Newest first. The game must be closed: quit it from its own menu "
                "before restoring. Your saves as they are now are backed up first, "
                "as \"Backup <date> (before restore)\", so a restore can be undone."
            ),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        listbox = tk.Listbox(frame, width=110, height=12, exportselection=False)
        listbox.pack(fill="both", expand=True)
        details = ttk.Label(frame, text="", wraplength=700, justify="left")
        details.pack(anchor="w", pady=(6, 0))
        scope = tk.StringVar(value="whole")
        slot_choice = tk.StringVar()
        options = ttk.Frame(frame)
        options.pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(
            options, text="The whole save folder", value="whole", variable=scope
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            options, text="One save slot only:", value="slot", variable=scope
        ).grid(row=1, column=0, sticky="w")
        slots = ttk.Combobox(options, textvariable=slot_choice, state="readonly", width=50)
        slots.grid(row=1, column=1, sticky="w", padx=(8, 0))
        entries: list[tuple[Path, object]] = []

        def describe(folder, info) -> str:
            villages = ", ".join(
                f"Save {slot}: {name or '(no name)'}" for slot, name in info.villages.items()
            ) or "no village saves"
            variant = folder.name.removeprefix(build.title + " - ")
            return (
                f"{info.label}   [{variant}]   {villages}   "
                f"{info.file_count} files, {vv_save_backup.describe_size(info.size)}"
            )

        def refresh() -> None:
            entries.clear()
            listbox.delete(0, "end")
            listed = [
                (folder, info)
                for folder in folders
                for info in vv_save_backup.list_backups(folder)
            ]
            listed.sort(key=lambda item: item[1].when, reverse=True)
            for folder, info in listed:
                entries.append((folder, info))
                listbox.insert("end", describe(folder, info))
            if entries:
                listbox.selection_set(0)
            selected()

        def current():
            chosen = listbox.curselection()
            return entries[chosen[0]] if chosen else None

        def selected(_event=None) -> None:
            item = current()
            if item is None:
                details.configure(text="")
                slots.configure(values=[])
                slot_choice.set("")
                return
            folder, info = item
            details.configure(text=f"Backup folder: {info.path}")
            values = [
                f"Save {slot}: {name or '(no name)'}" for slot, name in info.villages.items()
            ]
            slots.configure(values=values)
            slot_choice.set(values[0] if values else "")

        def chosen_slot():
            if scope.get() != "slot":
                return None
            text = slot_choice.get()
            if not text.startswith("Save "):
                return False
            return int(text.split(":", 1)[0].removeprefix("Save "))

        def restore() -> None:
            item = current()
            if item is None:
                return
            slot = chosen_slot()
            if slot is False:
                messagebox.showinfo(
                    "Restore Saves", "This backup holds no village save to choose.",
                    parent=dialog,
                )
                return
            self._run_restore(dialog, item[0], item[1], slot)
            # The "Please wait" window took the grab and released it on
            # closing; take it back so the main window stays inert behind
            # this one, as it was before the restore.
            if dialog.winfo_exists():
                dialog.grab_set()
            refresh()

        def delete() -> None:
            item = current()
            if item is None:
                return
            folder, info = item
            if not messagebox.askyesno(
                "Delete Backup",
                f"Delete this backup permanently?\n\n{describe(folder, info)}\n\n"
                f"{info.path}\n\nYour current saves are not affected.",
                parent=dialog,
            ):
                return
            try:
                vv_save_backup.delete_backup(folder, info.path)
            except (vv_save_backup.BackupError, OSError) as exc:
                messagebox.showerror("Delete Backup", str(exc), parent=dialog)
            refresh()

        listbox.bind("<<ListboxSelect>>", selected)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Restore...", command=restore).pack(side="left")
        ttk.Button(buttons, text="Delete Backup...", command=delete).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(
            side="left", padx=(8, 0)
        )
        refresh()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()
        dialog.focus_set()

    def _run_restore(self, parent, folder: Path, info, slot) -> None:
        """Confirm exactly what will change, then restore with the game closed."""
        if vv_save_backup.running_game_count(folder):
            messagebox.showerror(
                "Restore Saves",
                f"{vv_save_backup.game_exe_name(folder)} is running.\n\nQuit the game "
                "from its own menu first, then restore: a running game writes its "
                "village over the restored save when it quits. Nothing was changed.",
                parent=parent,
            )
            return
        try:
            # Hashes both copies of every file, which can take a while on a
            # network Documents: off the main thread, behind the wait window.
            plan = self._run_with_wait(
                "Checking the backup\u2026",
                lambda: vv_save_backup.plan_restore(folder, info.path, slot),
            )
        except (vv_save_backup.BackupError, OSError) as exc:
            messagebox.showerror("Restore Saves", str(exc), parent=parent)
            return
        if plan.changes == 0:
            messagebox.showinfo(
                "Restore Saves",
                "Your saves already match this backup; there is nothing to restore.",
                parent=parent,
            )
            return
        what = "the whole save folder" if slot is None else f"Save {slot} only"
        lines = (
            [f"Replace: {path}" for path in plan.replace]
            + [f"Add: {path}" for path in plan.add]
            + [f"Remove: {path}" for path in plan.remove]
        )
        shown = "\n".join(lines[:20])
        if len(lines) > 20:
            shown += f"\n... and {len(lines) - 20} more"
        if not messagebox.askyesno(
            "Restore Saves",
            f"Restore {what} of {folder.name} from the backup of {info.label}?\n\n"
            f"{len(plan.replace)} file(s) will be replaced, {len(plan.add)} added and "
            f"{len(plan.remove)} removed:\n\n{shown}\n\nYour saves as they are now "
            "are backed up first, so this can be undone.",
            parent=parent,
        ):
            return
        try:
            result = self._run_with_wait(
                "Restoring saves…",
                lambda: vv_save_backup.restore_backup(folder, info.path, slot),
            )
        except (vv_save_backup.BackupError, OSError) as exc:
            self.status_var.set("Restore Saves: the restore did not complete.")
            messagebox.showerror("Restore Saves", str(exc), parent=parent)
            return
        undo = (
            f"\n\nYour saves from before the restore are in:\n"
            f"{result.before_restore.backup_folder}"
            if result.before_restore
            else ""
        )
        self.status_var.set(f"Restore Saves: {folder.name} restored from {info.label}.")
        messagebox.showinfo(
            "Restore Saves",
            f"Restored {what} from the backup of {info.label}: every file was "
            f"checked against the backup.{undo}",
            parent=parent,
        )

    # -- Rename Tribe -------------------------------------------------------

    def _rename_single_tribe(self) -> None:
        """Rename Tribe for the game chosen on the One Game tab."""
        build = self._single_build()
        if build is not None:
            self._rename_tribe(build)

    def _rename_tribe(self, build) -> None:
        """Pick a game, its save folder and a slot, then type the new name.

        The slot list is read from the saves and is only for choosing; the
        counter and every refusal come from vv_tribe_rename, which holds each
        game's own limit. The rename itself runs off the main thread.
        """
        documents = vv_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                "Rename Tribe",
                "Windows did not report where your Documents folder is, so the "
                "save folders cannot be found.",
            )
            return
        titles = [item.title for item in self.builds]
        dialog = tk.Toplevel(self)
        dialog.title("Rename Tribe")
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                "Changes the tribe's name inside its save. The game must be "
                "closed: it saves when you quit it, which would put the old "
                "name back. The save folder is backed up first, into "
                "<save folder>\\Backups\\Backup <date and time> (before rename), "
                "and the patcher's logs get one line noting the new name."
            ),
            wraplength=560,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        game_var = tk.StringVar(value=build.title if build is not None else titles[0])
        folder_var = tk.StringVar()
        name_var = tk.StringVar()
        counter_var = tk.StringVar()
        problem_var = tk.StringVar()
        note_var = tk.StringVar()
        state: dict = {"folders": [], "slots": []}

        ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w")
        game_box = ttk.Combobox(
            frame, textvariable=game_var, values=titles, state="readonly", width=48
        )
        game_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Save folder:").grid(row=2, column=0, sticky="w")
        folder_box = ttk.Combobox(frame, textvariable=folder_var, state="readonly", width=48)
        folder_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Tribe:").grid(row=3, column=0, sticky="nw", pady=(4, 0))
        slot_list = tk.Listbox(frame, height=5, width=60, exportselection=False)
        slot_list.grid(row=3, column=1, columnspan=2, sticky="we", pady=(4, 2))
        ttk.Label(frame, text="New name:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        name_entry = ttk.Entry(frame, textvariable=name_var, width=36)
        name_entry.grid(row=4, column=1, sticky="w", pady=(8, 0))
        counter = ttk.Label(frame, textvariable=counter_var)
        counter.grid(row=4, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Label(
            frame, textvariable=problem_var, foreground="#a01010",
            wraplength=560, justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(
            frame, textvariable=note_var, wraplength=560, justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(2, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 0))
        rename_button = ttk.Button(buttons, text="Rename")
        rename_button.pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))

        def game() -> vv_tribe_rename.GameSaves:
            return vv_tribe_rename.game_for_title(game_var.get())

        def chosen_slot():
            picked = slot_list.curselection()
            if not picked:
                return None
            return state["slots"][picked[0]]

        def refresh_check(*_args) -> None:
            saves = game()
            name = name_var.get()
            counter_var.set(f"{len(name)} / {saves.max_length} characters")
            counter.configure(
                foreground="#a01010" if len(name) > saves.max_length else ""
            )
            problem = None
            info = chosen_slot()
            if not state["folders"]:
                problem = "No save folder was found for this game."
            elif info is None:
                problem = "Choose a tribe."
            elif info.problem:
                problem = info.problem
            elif name:
                problem = vv_tribe_rename.name_problem(saves, name)
                if problem is None and name == info.name:
                    problem = "That is already this tribe's name."
            problem_var.set(problem or "")
            note_var.set(
                "Allowed. The game's Change Tribe screen will show this name cut "
                "short, as it does long names the game itself makes; the game "
                "keeps and shows the whole name everywhere else."
                if problem is None and name and vv_tribe_rename.shown_shortened(saves, name)
                else ""
            )
            ok = problem is None and bool(name)
            rename_button.configure(state="normal" if ok else "disabled")

        def load_slots(*_args) -> None:
            slot_list.delete(0, "end")
            state["slots"] = []
            index = folder_box.current()
            if 0 <= index < len(state["folders"]):
                state["slots"] = vv_tribe_rename.read_slots(game(), state["folders"][index])
                for info in state["slots"]:
                    slot_list.insert("end", info.label)
                first = next(
                    (n for n, info in enumerate(state["slots"]) if not info.problem), None
                )
                if first is not None:
                    slot_list.selection_set(first)
            refresh_check()

        def load_folders(*_args) -> None:
            state["folders"] = vv_tribe_rename.rename_folders(game_var.get(), documents)
            folder_box.configure(values=[folder.name for folder in state["folders"]])
            if state["folders"]:
                folder_box.current(0)
            else:
                folder_var.set("")
            load_slots()

        def start() -> None:
            info = chosen_slot()
            if info is None or not state["folders"]:
                return
            folder = state["folders"][folder_box.current()]
            saves = game()
            new_name = name_var.get()
            problem = vv_tribe_rename.name_problem(saves, new_name)
            if problem is not None:
                messagebox.showerror("Rename Tribe", problem, parent=dialog)
                return
            if not messagebox.askyesno(
                "Rename Tribe",
                f"Rename \"{info.name}\" (Save {info.slot}) in {folder.name} to "
                f"\"{new_name}\"?\n\nThe save folder is backed up first.",
                parent=dialog,
            ):
                return
            try:
                result = self._run_with_wait(
                    "Renaming the tribe…\n\nThe save folder is backed up first.",
                    lambda: vv_tribe_rename.rename_tribe(saves, folder, info.slot, new_name),
                )
            except (vv_tribe_rename.RenameError, vv_save_backup.BackupError, OSError) as exc:
                self.status_var.set("Rename Tribe: nothing was renamed.")
                messagebox.showerror("Rename Tribe", str(exc), parent=dialog)
                load_slots()
                return
            self.status_var.set(
                f"Rename Tribe: {result.old_name} is now {result.new_name}."
            )
            messagebox.showinfo(
                "Rename Tribe",
                f"\"{result.old_name}\" is now \"{result.new_name}\" "
                f"(Save {result.slot}, {folder.name}).\n\n"
                f"{len(result.changed)} save file(s) changed and read back; "
                f"{len(result.notes)} log(s) noted the rename.\n\n"
                f"Backup: {result.backup.backup_folder}",
                parent=dialog,
            )
            name_var.set("")
            load_slots()

        rename_button.configure(command=start)
        game_box.bind("<<ComboboxSelected>>", load_folders)
        folder_box.bind("<<ComboboxSelected>>", load_slots)
        slot_list.bind("<<ListboxSelect>>", refresh_check)
        name_var.trace_add("write", refresh_check)
        frame.columnconfigure(1, weight=1)
        load_folders()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()
        name_entry.focus_set()

    # -- Check Logs / Repair Logs -------------------------------------------

    def _check_single_logs(self) -> None:
        """Check Logs for the game chosen on the One Game tab."""
        build = self._single_build()
        if build is not None:
            self._log_tool(build, repair=False)

    def _repair_single_logs(self) -> None:
        """Repair Logs for the game chosen on the One Game tab."""
        build = self._single_build()
        if build is not None:
            self._log_tool(build, repair=True)

    def _log_tool(self, build, repair: bool) -> None:
        """Pick a game, its save folder and a slot, then Check or Repair its logs.

        Check Logs runs the read-only checker (vv_log_tools.check_logs) and
        shows its report; it writes nothing, so it may run with the game open.
        Repair Logs repairs nothing itself: with the game closed it backs the
        folder up, clears the cross-check's markers and approves the repair
        (vv_log_tools.approve_repair), so the next time the village is played
        the game repairs it without asking.
        """
        title = "Repair Logs" if repair else "Check Logs"
        documents = vv_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                title,
                "Windows did not report where your Documents folder is, so the "
                "save folders cannot be found.",
            )
            return
        titles = [item.title for item in self.builds]
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        if repair:
            intro = (
                "Has the game repair this village's logs the next time you play it, "
                "without asking: everything confirmed wrong is put right, backed up "
                "and listed in the Repairs log. Nothing is repaired now. The game "
                "must be closed. The save folder is backed up first, into <save "
                "folder>\\Backups\\Backup <date and time> (before repair re-arm)."
            )
        else:
            intro = (
                "Checks every log and data file the patcher keeps for one village "
                "against its save, and shows what agrees and what does not. It only "
                "reads: nothing is changed, so the game may be running."
            )
        ttk.Label(frame, text=intro, wraplength=560, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )
        game_var = tk.StringVar(value=build.title if build is not None else titles[0])
        folder_var = tk.StringVar()
        problem_var = tk.StringVar()
        state: dict = {"folders": [], "slots": []}

        ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w")
        game_box = ttk.Combobox(
            frame, textvariable=game_var, values=titles, state="readonly", width=48
        )
        game_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Save folder:").grid(row=2, column=0, sticky="w")
        folder_box = ttk.Combobox(frame, textvariable=folder_var, state="readonly", width=48)
        folder_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Tribe:").grid(row=3, column=0, sticky="nw", pady=(4, 0))
        slot_list = tk.Listbox(frame, height=5, width=60, exportselection=False)
        slot_list.grid(row=3, column=1, columnspan=2, sticky="we", pady=(4, 2))
        ttk.Label(
            frame, textvariable=problem_var, foreground="#a01010",
            wraplength=560, justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))
        go_button = ttk.Button(buttons, text="Repair Logs" if repair else "Check")
        go_button.pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))

        def game() -> vv_tribe_rename.GameSaves:
            return vv_tribe_rename.game_for_title(game_var.get())

        def chosen():
            picked = slot_list.curselection()
            if not picked or not state["folders"]:
                return None
            info = state["slots"][picked[0]]
            return info if info.name is not None else None

        def refresh(*_args) -> None:
            problem = None
            if not state["folders"]:
                problem = "No save folder was found for this game."
            elif chosen() is None:
                problem = "Choose a tribe."
            problem_var.set(problem or "")
            go_button.configure(state="normal" if problem is None else "disabled")

        def load_slots(*_args) -> None:
            slot_list.delete(0, "end")
            state["slots"] = []
            index = folder_box.current()
            if 0 <= index < len(state["folders"]):
                state["slots"] = vv_tribe_rename.read_slots(game(), state["folders"][index])
                for info in state["slots"]:
                    slot_list.insert("end", info.label)
                first = next(
                    (n for n, info in enumerate(state["slots"]) if info.name is not None), None
                )
                if first is not None:
                    slot_list.selection_set(first)
            refresh()

        def load_folders(*_args) -> None:
            state["folders"] = vv_save_backup.find_save_folders(game_var.get(), documents)
            folder_box.configure(values=[folder.name for folder in state["folders"]])
            if state["folders"]:
                folder_box.current(0)
            else:
                folder_var.set("")
            load_slots()

        def start() -> None:
            info = chosen()
            if info is None:
                return
            folder = state["folders"][folder_box.current()]
            number = game().number
            if repair:
                self._repair_logs(dialog, folder, number, info)
            else:
                self._check_logs(dialog, folder, number, info)

        go_button.configure(command=start)
        game_box.bind("<<ComboboxSelected>>", load_folders)
        folder_box.bind("<<ComboboxSelected>>", load_slots)
        slot_list.bind("<<ListboxSelect>>", refresh)
        frame.columnconfigure(1, weight=1)
        load_folders()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.grab_set()

    def _check_logs(self, parent, folder: Path, number: int, info) -> None:
        """Run the read-only checker off the main thread and show its report."""
        try:
            result = self._run_with_wait(
                "Checking the logs…\n\nNothing is changed.",
                lambda: vv_log_tools.check_logs(folder, info.slot, number),
            )
        except (vv_log_tools.LogToolError, OSError) as exc:
            self.status_var.set("Check Logs: the logs could not be checked.")
            messagebox.showerror("Check Logs", str(exc), parent=parent)
            return
        self.status_var.set(f"Check Logs: {info.name}: {result.summary}")
        self._show_log_report(parent, folder, info, result)

    def _show_log_report(self, parent, folder: Path, info, result) -> None:
        """The checker's report, in a scrollable read-only window."""
        window = tk.Toplevel(parent)
        window.title(f"Check Logs - {info.name} (Save {info.slot})")
        window.transient(parent)
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=f"{folder.name}\n{info.name}: {result.summary}",
            font=("Segoe UI", 10, "bold"),
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "OK: agrees with the save.  WRONG: confirmed wrong (\"repairable\" "
                "says whether Repair Logs can have the game put it right).  NOTE: a "
                "difference that is not proof of an error.  UNCHECKED: nothing to "
                "check it against, or it could not be read."
            ),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        text = tk.Text(body, wrap="word", width=110, height=30)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure("WRONG", foreground="#a01010")
        text.tag_configure("file", font=("Segoe UI", 9, "bold"))
        for line in result.text.splitlines():
            verdict = line.split(None, 1)[0] if line.strip() else ""
            tag = "file" if line.startswith("== ") else ("WRONG" if verdict == "WRONG" else ())
            text.insert("end", line + "\n", tag)
        text.insert("end", f"\n{result.summary}\n", "file")
        text.configure(state="disabled")
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e", pady=(8, 0))

    def _repair_logs(self, parent, folder: Path, number: int, info) -> None:
        """Approve the repair of one slot's village, with the game closed."""
        exe = vv_save_backup.game_exe_name(folder)
        if vv_save_backup.running_game_count(folder):
            messagebox.showerror(
                "Repair Logs",
                f"{exe} is running.\n\nQuit the game first (from its own menu), "
                "then choose Repair Logs again. Repair Logs never pauses or closes "
                "a game. Nothing was changed.",
                parent=parent,
            )
            return
        try:
            checked = self._run_with_wait(
                "Checking the logs…\n\nNothing is changed.",
                lambda: vv_log_tools.check_logs(folder, info.slot, number),
            )
            found = (
                f"The read-only check finds {checked.wrong} confirmed wrong "
                f"({checked.summary})"
                if checked.wrong
                else "The read-only check finds nothing confirmed wrong in "
                f"{info.name}'s logs. You can still have the game check them "
                "again, and repair whatever it finds, the next time you play it."
            )
        except (vv_log_tools.LogToolError, OSError) as exc:
            found = f"The logs could not be checked here ({exc})."
        if not messagebox.askyesno(
            "Repair Logs",
            f"{found}\n\nThe next time you play {info.name}, the game will check "
            "its logs and repair everything confirmed wrong WITHOUT asking (every "
            "change is backed up and listed in the Repairs log). Nothing is repaired "
            f"now.\n\nThe save folder {folder.name} is backed up first. Continue?",
            parent=parent,
        ):
            return
        try:
            result = self._run_with_wait(
                "Preparing the repair…\n\nThe save folder is backed up first.",
                lambda: vv_log_tools.approve_repair(folder, number, info.slot),
            )
        except (vv_log_tools.LogToolError, vv_save_backup.BackupError, OSError) as exc:
            self.status_var.set("Repair Logs: nothing was changed.")
            messagebox.showerror("Repair Logs", str(exc), parent=parent)
            return
        self.status_var.set(
            f"Repair Logs: {info.name} will be repaired the next time it is played."
        )
        messagebox.showinfo(
            "Repair Logs",
            f"The next time you play {info.name} (Save {info.slot}), the game will "
            "repair its logs without asking, then close normally from its own menu "
            "so the repairs are saved.\n\n"
            f"{len(result.cleared)} \"already checked\" marker(s) cleared.\n\n"
            f"Backup: {result.backup.backup_folder}",
            parent=parent,
        )

    def _close(self) -> None:
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
