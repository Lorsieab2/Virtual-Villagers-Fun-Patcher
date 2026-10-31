"""The Copy Player Slot window (Tools tab): pick a game, its save folder, the village to copy, an empty
slot and a name; confirm; then src/vv_copy_slot.py copies it off the main thread.

The owner: "All 'Copy Player Slot' should have a confirmation prompt too", with No as the default (Enter
never copies).  Answering No writes nothing, not even the backup (`confirm_and_copy`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import messagebox, ttk

import vv_copy_slot
import vv_save_backup
import vv_tribe_rename

TITLE = "Copy Player Slot"


def confirmation_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, new_name: str) -> str:
    return (
        f"Copy \"{source.name}\" (Save {source.slot}) to the empty Save {target} as \"{new_name}\"?\n\n"
        f"Save folder: {folder.name}\n\n"
        "The save folder is backed up first, into Backups\\Backup <date and time> (before copy). "
        f"\"{source.name}\" itself is not changed."
    )


def confirm_and_copy(
    ask: Callable[..., bool],
    run: Callable[[Callable[[], vv_copy_slot.CopyResult]], vv_copy_slot.CopyResult],
    game: vv_tribe_rename.GameSaves,
    folder: Path,
    source: vv_tribe_rename.SlotInfo,
    target: int,
    new_name: str,
    parent=None,
    processes=None,
) -> vv_copy_slot.CopyResult | None:
    """Ask first (No is the default button); only a Yes backs up and copies.  None when the player said
    No: then nothing at all was written."""
    if not ask(TITLE, confirmation_text(folder, source, target, new_name), parent=parent, default="no",
               icon="question"):
        return None
    return run(lambda: vv_copy_slot.copy_slot(game, folder, source.slot, target, new_name, processes=processes))


def open_copy_slot(app, build) -> None:
    """The window, for ``build`` (a game from the One Game tab) or, with None, any of the five."""
    from vv_fun_patcher_gui import _regrab
    from vv_tree_editor_tools import scrollable_frame

    documents = vv_save_backup.documents_folder()
    if documents is None:
        messagebox.showerror(TITLE, "Windows did not report where your Documents folder is, so the save "
                                    "folders cannot be found.")
        return
    titles = [item.title for item in app.builds]
    dialog = tk.Toplevel(app)
    dialog.title(TITLE)
    dialog.transient(app)
    frame = scrollable_frame(dialog, padding=16)
    ttk.Label(
        frame,
        text=(
            "Copies a village into an empty slot of the same save folder, under a new name, with "
            "everything the patcher keeps for it (its logs and data). The game must be closed. The "
            "save folder is backed up first, into <save folder>\\Backups\\Backup <date and time> "
            "(before copy). The village you copy from is not changed."
        ),
        wraplength=560, justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    game_var = tk.StringVar(value=build.title if build is not None else titles[0])
    folder_var, source_var, target_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    name_var, counter_var, problem_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    state: dict = {"folders": [], "slots": None}

    ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w")
    game_box = ttk.Combobox(frame, textvariable=game_var, values=titles, state="readonly", width=48)
    game_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="Save folder:").grid(row=2, column=0, sticky="w")
    folder_box = ttk.Combobox(frame, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="Copy from:").grid(row=3, column=0, sticky="w")
    source_box = ttk.Combobox(frame, textvariable=source_var, state="readonly", width=48)
    source_box.grid(row=3, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="Copy to:").grid(row=4, column=0, sticky="w")
    target_box = ttk.Combobox(frame, textvariable=target_var, state="readonly", width=48)
    target_box.grid(row=4, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="New name:").grid(row=5, column=0, sticky="w", pady=(8, 0))
    name_entry = ttk.Entry(frame, textvariable=name_var, width=36)
    name_entry.grid(row=5, column=1, sticky="w", pady=(8, 0))
    counter = ttk.Label(frame, textvariable=counter_var)
    counter.grid(row=5, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=560, justify="left").grid(
        row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 0))
    copy_button = ttk.Button(buttons, text="Copy...")
    copy_button.pack(side="left")
    ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))

    def game() -> vv_tribe_rename.GameSaves:
        return vv_tribe_rename.game_for_title(game_var.get())

    def chosen():
        slots = state["slots"]
        if slots is None or not state["folders"]:
            return None, None
        s, t = source_box.current(), target_box.current()
        source = slots.sources[s] if 0 <= s < len(slots.sources) else None
        target = slots.targets[t] if 0 <= t < len(slots.targets) else None
        return source, target

    def refresh(*_args) -> None:
        saves = game()
        name = name_var.get()
        counter_var.set(f"{len(name)} / {saves.max_length} characters")
        counter.configure(foreground="#a01010" if len(name) > saves.max_length else "")
        source, target = chosen()
        problem = None
        if not state["folders"]:
            problem = "No save folder was found for this game."
        elif source is None:
            problem = "This save folder has no village to copy."
        elif target is None:
            problem = "Every slot is in use: there is no empty slot to copy to."
        elif name:
            problem = vv_tribe_rename.name_problem(saves, name)
        problem_var.set(problem or "")
        copy_button.configure(state="normal" if problem is None and name else "disabled")

    def load_slots(*_args) -> None:
        index = folder_box.current()
        state["slots"] = None
        if 0 <= index < len(state["folders"]):
            state["slots"] = vv_copy_slot.read_slots(game(), state["folders"][index])
        slots = state["slots"]
        sources = [info.label for info in slots.sources] if slots else []
        targets = [f"Save {slot}: (empty)" for slot in slots.targets] if slots else []
        source_box.configure(values=sources)
        target_box.configure(values=targets)
        source_var.set(sources[0] if sources else "")
        target_var.set(targets[0] if targets else "")
        if sources:
            source_box.current(0)
        if targets:
            target_box.current(0)
        refresh()

    def load_folders(*_args) -> None:
        state["folders"] = vv_copy_slot.copy_folders(game_var.get(), documents)
        folder_box.configure(values=[folder.name for folder in state["folders"]])
        if state["folders"]:
            folder_box.current(0)
        else:
            folder_var.set("")
        load_slots()

    def start() -> None:
        source, target = chosen()
        if source is None or target is None:
            return
        folder = state["folders"][folder_box.current()]
        saves = game()
        new_name = name_var.get()
        problem = vv_tribe_rename.name_problem(saves, new_name)
        if problem is not None:
            messagebox.showerror(TITLE, problem, parent=dialog)
            return
        try:
            result = confirm_and_copy(
                messagebox.askyesno,
                lambda work: app._run_with_wait("Copying the slot…\n\nThe save folder is backed up first.", work),
                saves, folder, source, target, new_name, parent=dialog)
        except (vv_copy_slot.CopyError, vv_save_backup.BackupError, OSError) as exc:
            _regrab(dialog)
            app.status_var.set("Copy Player Slot: nothing was copied.")
            messagebox.showerror(TITLE, str(exc), parent=dialog)
            load_slots()
            return
        _regrab(dialog)
        if result is None:
            app.status_var.set("Copy Player Slot: nothing was copied.")
            return
        app.status_var.set(f"Copy Player Slot: {result.old_name} copied to Save {result.target} as {result.new_name}.")
        skipped = ("\n\nNot copied:\n" + "\n".join(result.skipped)) if result.skipped else ""
        messagebox.showinfo(
            TITLE,
            f"\"{result.old_name}\" (Save {result.source}) was copied to Save {result.target} as "
            f"\"{result.new_name}\" ({folder.name}).\n\n{len(result.created)} file(s) made and read back."
            f"{skipped}\n\nBackup: {result.backup.backup_folder}",
            parent=dialog,
        )
        name_var.set("")
        load_slots()

    copy_button.configure(command=start)
    game_box.bind("<<ComboboxSelected>>", load_folders)
    folder_box.bind("<<ComboboxSelected>>", load_slots)
    source_box.bind("<<ComboboxSelected>>", refresh)
    target_box.bind("<<ComboboxSelected>>", refresh)
    name_var.trace_add("write", refresh)
    frame.columnconfigure(1, weight=1)
    load_folders()
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.update_idletasks()
    dialog.grab_set()
    name_entry.focus_set()
