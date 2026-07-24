from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vv_fun_patcher import (
    DEFAULT_PATCH_MODE,
    PatcherError,
    apply_all,
    apply_patch,
    dry_run,
    dry_run_all,
    get_patch_mode,
    get_patch_variant,
    identify,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    validate_all_sources,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "patcher_local_settings.json"


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
        self.builds = load_builds()
        self.patch_modes = load_patch_modes()
        self.fun_patches = load_fun_patches()
        self.fun_patch_vars = {
            patch.id: tk.BooleanVar(value=False) for patch in self.fun_patches
        }
        self.exe_var = tk.StringVar()
        self.patch_mode_var = tk.StringVar(value=DEFAULT_PATCH_MODE)
        self.all_folder_vars = {build.id: tk.StringVar() for build in self.builds}
        self.status_var = tk.StringVar(value="Choose a patch style and one game or all five.")
        self.game_var = tk.StringVar(value="No game identified yet")
        self.last_output_dir: Path | None = None
        self.last_modified_paths: dict[str, Path] = {}
        self._load_settings()
        self._build_ui()
        self._mode_changed(save=False)
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        ttk.Label(
            outer,
            text="Creates a verified complete copy of each game folder and adds the modified EXE there. Originals are never replaced.",
        ).pack(anchor="w", pady=(0, 10))
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

        mode_box = ttk.LabelFrame(outer, text="Patch style", padding=10)
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
        for offset, patch in enumerate(self.fun_patches):
            ttk.Checkbutton(
                mode_box,
                text=f"{patch.name} ({patch.game_id.upper()})",
                variable=self.fun_patch_vars[patch.id],
                command=self._fun_patch_changed,
            ).grid(row=fun_row + 1 + offset * 2, column=1, sticky="w", pady=3)
            ttk.Label(mode_box, text=patch.description, wraplength=620).grid(
                row=fun_row + 2 + offset * 2, column=1, sticky="w", pady=(0, 3)
            )
        mode_box.columnconfigure(1, weight=1)

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
            text="Choose one game folder per row. Each result is a complete sibling copy containing all original files plus the modified EXE.",
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

    def _mode(self) -> str:
        return self.patch_mode_var.get()

    def _mode_changed(self, save: bool = True) -> None:
        try:
            mode = get_patch_mode(self._mode())
        except PatcherError:
            self.patch_mode_var.set(DEFAULT_PATCH_MODE)
            mode = get_patch_mode(DEFAULT_PATCH_MODE)
        if mode.id == "collection_progression":
            detail = (
                "Collections still raise the cap and are needed to reach the absolute maximum. "
                "In The Secret City, level-3 magic also remains part of the bonus."
            )
        elif mode.id == "immediate_fixed":
            detail = (
                "The absolute maximum is available immediately. Collections no longer change it; "
                "in The Secret City, magic tech no longer changes it either."
            )
        elif mode.id == "experimental_expanded_256":
            detail = (
                "Experimental: VV3-VV5 expand their physical records and save layout from 150 to 256. "
                "Their differently named EXEs use separate executable-named save folders. "
                "VV1-VV2 use their existing 256 slots. Collections no longer change the cap."
            )
        else:
            detail = (
                "Experimental progression: VV3-VV5 expand to 256 records. Collections, "
                "and The Secret City's level-3 Magic bonus, retain their original effects "
                "and are needed to reach 256. Modified EXEs use separate save folders."
            )
        self.mode_detail_var.set(detail)
        self.status_var.set(f"Selected: {mode.name}. {detail}")
        if save:
            self._save_settings()

    def _selected_fun_patch_ids(self, game_id: str | None = None) -> list[str]:
        return [
            patch.id
            for patch in self.fun_patches
            if self.fun_patch_vars[patch.id].get()
            and (game_id is None or patch.game_id == game_id)
        ]

    def _fun_patch_changed(self) -> None:
        selected = [
            patch.name
            for patch in self.fun_patches
            if self.fun_patch_vars[patch.id].get()
        ]
        self.status_var.set(
            "Additional patches: " + (", ".join(selected) if selected else "none")
        )
        self._save_settings()

    def _load_settings(self) -> None:
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        saved_mode = data.get("patch_mode", DEFAULT_PATCH_MODE)
        if saved_mode in {mode.id for mode in self.patch_modes}:
            self.patch_mode_var.set(saved_mode)
        selected_fun = data.get("fun_patches", [])
        if isinstance(selected_fun, list):
            for patch in self.fun_patches:
                self.fun_patch_vars[patch.id].set(patch.id in selected_fun)
        self.exe_var.set(data.get("original_exe", ""))
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
        if mode.id == "collection_progression":
            text = "collection bonuses remain active and are needed for the absolute maximum."
        elif mode.id == "immediate_fixed":
            text = "the absolute maximum is immediate; collection bonuses do not affect it."
        elif mode.id == "experimental_expanded_256":
            text = (
                "experimental 256 mode is immediate. VV3-VV5 use expanded records and "
                "the modified EXEs use their own executable-named save folders."
            )
        else:
            text = (
                "experimental 256 collection progression is active. Collections, and "
                "VV3 Magic Tech, retain their original bonuses and are needed to reach 256."
            )
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
            validated = validate_all_sources(self._all_sources())
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
            result = dry_run(
                source, self._mode(), self._selected_fun_patch_ids(build.id)
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
            results = dry_run_all(
                self._all_sources(), self._mode(), self._selected_fun_patch_ids()
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

    def _apply(self) -> None:
        try:
            source = self._source()
            build = identify(source)
            preview = dry_run(
                source, self._mode(), self._selected_fun_patch_ids(build.id)
            )
            if not self._confirm_experimental():
                return
            output_folder = Path(preview["output_folder"])
            overwrite = False
            if output_folder.exists():
                overwrite = messagebox.askyesno(
                    "Replace existing copied game folder?",
                    f"This complete copied game folder already exists:\n\n{output_folder}\n\nReplace the whole copied folder with a newly verified copy of the selected original?",
                )
                if not overwrite:
                    return
            output, log = apply_patch(
                source, self._mode(), overwrite=overwrite,
                fun_patch_ids=self._selected_fun_patch_ids(build.id),
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
            sources = self._all_sources()
            validated = validate_all_sources(sources)
            previews = dry_run_all(
                sources, self._mode(), self._selected_fun_patch_ids()
            )
            if not self._confirm_experimental():
                return
            existing = []
            for (build, source), preview in zip(validated, previews):
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
            results = apply_all(
                sources, self._mode(), overwrite=overwrite,
                fun_patch_ids=self._selected_fun_patch_ids(),
            )
            self.last_output_dir = results[0][0].parent
            self.last_modified_paths = {
                build.id: output
                for (build, _), (output, _) in zip(validated, results)
            }
            self.open_button.configure(text="Open First Game Folder", state="normal")
            self.status_var.set("Success. Created all five modified game folders.")
            self._save_settings()
            self._show_folder_confirmation(
                "All five modified games created",
                [
                    (build.title, source.parent, output.parent)
                    for (build, source), (output, _) in zip(validated, results)
                ],
            )
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Batch patch failed", str(exc))

    def _confirm_experimental(self) -> bool:
        if self._mode() not in {
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        }:
            return True
        return messagebox.askyesno(
            "Use experimental expanded saves?",
            "Experimental mode gives VV3, VV4, and VV5 an expanded 256-record save "
            "layout. Full 256-villager long-play testing is not complete.\n\nContinue?",
        )

    def _show_folder_confirmation(
        self,
        title: str,
        rows: list[tuple[str, Path, Path]],
    ) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=16)
        frame.grid(sticky="nsew")
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
        link = tk.Label(
            parent,
            text=text,
            foreground="#0563C1",
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        link.bind("<Button-1>", lambda _event: command())
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
                    )
                    target = Path(preview["output_folder"])
                except (PatcherError, OSError) as exc:
                    self.status_var.set(str(exc))
                    messagebox.showerror("Cannot locate modified folder", str(exc))
                    return
        self._open_folder(target)

    def _close(self) -> None:
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
