from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vv_fun_patcher import PatcherError, apply_patch, dry_run, identify

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "patcher_local_settings.json"

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Virtual Villagers Fun Patcher")
        self.geometry("760x470")
        self.minsize(680, 430)
        self.exe_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose one of the five original Virtual Villagers EXEs.")
        self.game_var = tk.StringVar(value="No game identified yet")
        self.last_output: Path | None = None
        self._load_settings()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Virtual Villagers Fun Patcher", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Miscellaneous fun patches for all five classic PC games", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 18))

        input_box = ttk.LabelFrame(outer, text="Original game executable", padding=12)
        input_box.pack(fill="x")
        ttk.Entry(input_box, textvariable=self.exe_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(input_box, text="Browse…", command=self._browse_exe).grid(row=0, column=1)
        input_box.columnconfigure(0, weight=1)
        ttk.Label(input_box, textvariable=self.game_var, foreground="#245a9a").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        output_box = ttk.LabelFrame(outer, text="Output folder", padding=12)
        output_box.pack(fill="x", pady=12)
        ttk.Entry(output_box, textvariable=self.output_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(output_box, text="Browse…", command=self._browse_output).grid(row=0, column=1)
        output_box.columnconfigure(0, weight=1)

        note = "Your original EXE is never changed. The patcher creates a separate ‘- Modified Max Pop.exe’ copy and a verification log."
        ttk.Label(outer, text=note, wraplength=700).pack(anchor="w", pady=(2, 14))

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        ttk.Button(actions, text="Validate", command=self._validate).pack(side="left")
        ttk.Button(actions, text="Dry Run", command=self._dry_run).pack(side="left", padx=8)
        ttk.Button(actions, text="Create Modified EXE", command=self._apply).pack(side="left")
        self.open_button = ttk.Button(actions, text="Open Output Folder", command=self._open_output, state="disabled")
        self.open_button.pack(side="right")

        status_box = ttk.LabelFrame(outer, text="Status", padding=12)
        status_box.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(status_box, textvariable=self.status_var, wraplength=690, justify="left").pack(anchor="w")

    def _load_settings(self) -> None:
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.exe_var.set(data.get("original_exe", ""))
        self.output_var.set(data.get("output_dir", str(ROOT / "outputs")))

    def _save_settings(self) -> None:
        data = {"original_exe":self.exe_var.get().strip(),"output_dir":self.output_var.get().strip()}
        SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _browse_exe(self) -> None:
        current = Path(self.exe_var.get()).parent if self.exe_var.get() else Path.home()
        chosen = filedialog.askopenfilename(title="Choose the original Virtual Villagers EXE", initialdir=current, filetypes=[("Windows executables", "*.exe"), ("All files", "*.*")])
        if chosen:
            self.exe_var.set(chosen)
            self._save_settings()
            self._validate(show_popup=False)

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(title="Choose output folder", initialdir=self.output_var.get() or ROOT)
        if chosen:
            self.output_var.set(chosen)
            self._save_settings()

    def _source(self) -> Path:
        value = self.exe_var.get().strip()
        if not value:
            raise PatcherError("Choose an original game executable first.")
        return Path(value)

    def _validate(self, show_popup: bool = True) -> None:
        try:
            build = identify(self._source())
            self.game_var.set(f"Supported build: {build.title} — target {build.villager_slots} villager slots")
            self.status_var.set(f"Validated {build.title}. The exact stock SHA-256 and every guarded patch byte match.")
            self._save_settings()
            if show_popup:
                messagebox.showinfo("Validated", self.status_var.get())
        except PatcherError as exc:
            self.game_var.set("Unsupported or unrecognized executable")
            self.status_var.set(str(exc))
            if show_popup:
                messagebox.showerror("Cannot validate", str(exc))

    def _dry_run(self) -> None:
        try:
            result = dry_run(self._source())
            self.game_var.set(f"Supported build: {result['game']} — target {result['villager_slots']} villager slots")
            self.status_var.set("Dry run passed. No files were written. Planned output:\n" + result["output_name"] + "\nExpected SHA-256: " + result["result_sha256"])
            self._save_settings()
            messagebox.showinfo("Dry run passed", self.status_var.get())
        except PatcherError as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Dry run failed", str(exc))

    def _apply(self) -> None:
        try:
            source = self._source()
            output_dir = Path(self.output_var.get().strip() or ROOT / "outputs")
            build = identify(source)
            output = output_dir / build.output_name
            overwrite = False
            if output.exists():
                overwrite = messagebox.askyesno("Replace existing output?", f"This file already exists:\n\n{output}\n\nReplace it with a newly verified copy?")
                if not overwrite:
                    return
            output, log = apply_patch(source, output_dir, overwrite=overwrite)
            self.last_output = output
            self.open_button.configure(state="normal")
            self.status_var.set(f"Success. Created and verified:\n{output}\n\nVerification log:\n{log}")
            self._save_settings()
            messagebox.showinfo("Modified EXE created", self.status_var.get())
        except (PatcherError, OSError) as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Patch failed", str(exc))

    def _open_output(self) -> None:
        folder = self.last_output.parent if self.last_output else Path(self.output_var.get())
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _close(self) -> None:
        self._save_settings()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
