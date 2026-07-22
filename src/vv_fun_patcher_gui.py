from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vv_fun_patcher import (
    PatcherError,
    apply_all,
    apply_patch,
    dry_run,
    dry_run_all,
    identify,
    load_builds,
    validate_all_sources,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "patcher_local_settings.json"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Virtual Villagers Fun Patcher")
        self.geometry("900x680")
        self.minsize(780, 600)
        self.builds = load_builds()
        self.exe_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.all_folder_vars = {build.id: tk.StringVar() for build in self.builds}
        self.status_var = tk.StringVar(value="Choose one game, or select all five together.")
        self.game_var = tk.StringVar(value="No game identified yet")
        self.last_output_dir: Path | None = None
        self._load_settings()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Virtual Villagers Fun Patcher", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Miscellaneous fun patches for all five classic PC games",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        single_tab = ttk.Frame(notebook, padding=14)
        all_tab = ttk.Frame(notebook, padding=14)
        notebook.add(single_tab, text="One Game")
        notebook.add(all_tab, text="All 5 Games")

        self._build_single_tab(single_tab)
        self._build_all_tab(all_tab)

        output_box = ttk.LabelFrame(outer, text="Output folder", padding=10)
        output_box.pack(fill="x", pady=(12, 0))
        ttk.Entry(output_box, textvariable=self.output_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(output_box, text="Browse...", command=self._browse_output).grid(row=0, column=1)
        output_box.columnconfigure(0, weight=1)

        status_box = ttk.LabelFrame(outer, text="Status", padding=10)
        status_box.pack(fill="x", pady=(10, 0))
        ttk.Label(status_box, textvariable=self.status_var, wraplength=830, justify="left").pack(anchor="w")

        self.open_button = ttk.Button(
            status_box, text="Open Output Folder", command=self._open_output, state="disabled"
        )
        self.open_button.pack(anchor="e", pady=(8, 0))

    def _build_single_tab(self, tab: ttk.Frame) -> None:
        input_box = ttk.LabelFrame(tab, text="Original game executable", padding=10)
        input_box.pack(fill="x")
        ttk.Entry(input_box, textvariable=self.exe_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(input_box, text="Browse...", command=self._browse_exe).grid(row=0, column=1)
        input_box.columnconfigure(0, weight=1)
        ttk.Label(input_box, textvariable=self.game_var, foreground="#245a9a").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        ttk.Label(
            tab,
            text="The original EXE is never changed. A separate '- Modified Max Pop.exe' copy and verification log are created.",
            wraplength=800,
        ).pack(anchor="w", pady=(12, 12))

        actions = ttk.Frame(tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Validate", command=self._validate).pack(side="left")
        ttk.Button(actions, text="Dry Run", command=self._dry_run).pack(side="left", padx=8)
        ttk.Button(actions, text="Create Modified EXE", command=self._apply).pack(side="left")

    def _build_all_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(
            tab,
            text="Choose one game folder per row. The patcher finds and validates the expected EXE inside each folder before writing.",
            wraplength=800,
        ).pack(anchor="w", pady=(0, 8))

        grid = ttk.Frame(tab)
        grid.pack(fill="both", expand=True)
        for row, build in enumerate(self.builds):
            short_title = build.title.removeprefix("Virtual Villagers - ")
            ttk.Label(grid, text=f"{row + 1}. {short_title} ({build.villager_slots} slots)").grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=4
            )
            ttk.Entry(grid, textvariable=self.all_folder_vars[build.id]).grid(
                row=row, column=1, sticky="ew", padx=(0, 8), pady=4
            )
            ttk.Button(
                grid,
                text="Choose Folder...",
                command=lambda game_id=build.id: self._browse_bulk_folder(game_id),
            ).grid(row=row, column=2, pady=4)
        grid.columnconfigure(1, weight=1)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Find All 5 in Parent Folder...", command=self._find_all).pack(side="left")
        ttk.Button(actions, text="Validate All 5", command=self._validate_all).pack(side="left", padx=(16, 8))
        ttk.Button(actions, text="Dry Run All 5", command=self._dry_run_all).pack(side="left")
        ttk.Button(actions, text="Patch All 5", command=self._apply_all).pack(side="left", padx=(8, 0))

    def _load_settings(self) -> None:
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}
        self.exe_var.set(data.get("original_exe", ""))
        self.output_var.set(data.get("output_dir", str(ROOT / "outputs")))
        saved_all = data.get("all_game_folders", data.get("all_game_exes", {}))
        if isinstance(saved_all, dict):
            for build in self.builds:
                value = saved_all.get(build.id, "")
                if isinstance(value, str):
                    saved_path = Path(value)
                    if saved_path.name.casefold() == build.input_name.casefold():
                        value = str(saved_path.parent)
                    self.all_folder_vars[build.id].set(value)

    def _save_settings(self) -> None:
        data = {
            "original_exe": self.exe_var.get().strip(),
            "output_dir": self.output_var.get().strip(),
            "all_game_folders": {
                build.id: self.all_folder_vars[build.id].get().strip() for build in self.builds
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

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(
            title="Choose output folder", initialdir=self.output_var.get() or ROOT
        )
        if chosen:
            self.output_var.set(chosen)
            self._save_settings()

    def _find_all(self) -> None:
        chosen = filedialog.askdirectory(
            title="Choose the parent folder containing the five game folders",
            initialdir=Path.home(),
        )
        if not chosen:
            return
        root = Path(chosen)
        children = []
        try:
            children = [path for path in root.iterdir() if path.is_dir()]
        except OSError as exc:
            messagebox.showerror("Cannot search folder", str(exc))
            return
        found = 0
        problems: list[str] = []
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
        self.status_var.set(f"Found {found} of 5 original EXEs." + ("\n" + "\n".join(problems) if problems else ""))
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
        values = {build.id: self.all_folder_vars[build.id].get().strip() for build in self.builds}
        missing = [build.title for build in self.builds if not values[build.id]]
        if missing:
            raise PatcherError("Choose all five original game folders. Missing: " + ", ".join(missing))
        return {game_id: Path(value) for game_id, value in values.items()}

    def _output_dir(self) -> Path:
        return Path(self.output_var.get().strip() or ROOT / "outputs")

    def _validate(self, show_popup: bool = True) -> None:
        try:
            build = identify(self._source())
            self.game_var.set(
                f"Supported build: {build.title} - target {build.villager_slots} villager slots"
            )
            self.status_var.set(
                f"Validated {build.title}. The exact stock SHA-256 and every guarded patch byte match."
            )
            self._save_settings()
            if show_popup:
                messagebox.showinfo("Validated", self.status_var.get())
        except PatcherError as exc:
            self.game_var.set("Unsupported or unrecognized executable")
            self.status_var.set(str(exc))
            if show_popup:
                messagebox.showerror("Cannot validate", str(exc))

    def _validate_all(self) -> None:
        try:
            validated = validate_all_sources(self._all_sources())
            self.status_var.set(
                "All five exact stock builds validated:\n"
                + "\n".join(f"- {build.title}" for build, _ in validated)
            )
            self._save_settings()
            messagebox.showinfo("All five validated", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Cannot validate all five", str(exc))

    def _dry_run(self) -> None:
        try:
            result = dry_run(self._source())
            self.game_var.set(
                f"Supported build: {result['game']} - target {result['villager_slots']} villager slots"
            )
            self.status_var.set(
                "Dry run passed. No files were written. Planned output:\n"
                + result["output_name"]
                + "\nExpected SHA-256: "
                + result["result_sha256"]
            )
            self._save_settings()
            messagebox.showinfo("Dry run passed", self.status_var.get())
        except PatcherError as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Dry run failed", str(exc))

    def _dry_run_all(self) -> None:
        try:
            results = dry_run_all(self._all_sources())
            self.status_var.set(
                "All-five dry run passed. No files were written:\n"
                + "\n".join(f"- {result['output_name']}" for result in results)
            )
            self._save_settings()
            messagebox.showinfo("All-five dry run passed", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("All-five dry run failed", str(exc))

    def _apply(self) -> None:
        try:
            source = self._source()
            output_dir = self._output_dir()
            build = identify(source)
            output = output_dir / build.output_name
            overwrite = False
            if output.exists():
                overwrite = messagebox.askyesno(
                    "Replace existing output?",
                    f"This file already exists:\n\n{output}\n\nReplace it with a newly verified copy?",
                )
                if not overwrite:
                    return
            output, log = apply_patch(source, output_dir, overwrite=overwrite)
            self.last_output_dir = output.parent
            self.open_button.configure(state="normal")
            self.status_var.set(f"Success. Created and verified:\n{output}\n\nVerification log:\n{log}")
            self._save_settings()
            messagebox.showinfo("Modified EXE created", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Patch failed", str(exc))

    def _apply_all(self) -> None:
        try:
            sources = self._all_sources()
            output_dir = self._output_dir()
            validated = validate_all_sources(sources)
            existing = [
                output_dir / build.output_name
                for build, _ in validated
                if (output_dir / build.output_name).exists()
            ]
            overwrite = False
            if existing:
                overwrite = messagebox.askyesno(
                    "Replace existing batch outputs?",
                    "One or more batch outputs already exist:\n\n"
                    + "\n".join(str(path) for path in existing)
                    + "\n\nReplace them and create a newly verified set of all five?",
                )
                if not overwrite:
                    return
            results = apply_all(sources, output_dir, overwrite=overwrite)
            self.last_output_dir = output_dir.resolve()
            self.open_button.configure(state="normal")
            self.status_var.set(
                "Success. All five modified EXEs were created and verified:\n"
                + "\n".join(f"- {output}" for output, _ in results)
            )
            self._save_settings()
            messagebox.showinfo("All five modified EXEs created", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Batch patch failed", str(exc))

    def _open_output(self) -> None:
        folder = self.last_output_dir or self._output_dir()
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _close(self) -> None:
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
