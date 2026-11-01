"""The Copy Player Slot window (Tools tab): pick a game, its save folder, the village to copy, the slot to
copy it to and a name; confirm; then src/vv_copy_slot.py copies it off the main thread.

The owner: "All 'Copy Player Slot' should have a confirmation prompt too", then "I want the Copy Player
slot to be able to overwrite existing slots (with a confirmation prompt of course)".  "Copy to" lists every
slot but the source; a slot that holds a player says "(will be overwritten)" and gets its own question.
No is the default; Return and Escape answer No (`ask_yes_no`).  Answering No writes nothing, not even the
backup (`confirm_and_copy`).  The prompts' words are the ones every patcher shares.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import messagebox, ttk

import vv_copy_slot
import vv_save_backup
import vv_tribe_rename

TITLE = "Copy Player Slot"
# The most set-aside leftover files named one by one in the question; the rest are counted.
SHOWN_LEFTOVERS = 25


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H-%M-%S")


def replace_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, old_name: str, new_name: str,
                 when: datetime) -> str:
    """The question for a target slot that holds a player (the patchers' shared words)."""
    return (f"Save {target} holds the {old_name} village. It will be replaced by a copy of {source.name} "
            f"(Save {source.slot}), named {new_name}. The whole save folder ({folder}) is backed up first, and "
            f"{old_name}'s files are kept in Backups\\Replaced by copy {_stamp(when)}. Replace it?")


def empty_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, new_name: str, when: datetime,
               leftovers: list[Path] | None = None) -> str:
    """The question for an empty target slot (the patchers' shared words), with its leftovers listed."""
    text = (f"Save {target} is empty. It will get a copy of {source.name} (Save {source.slot}), named {new_name}. "
            f"The whole save folder ({folder}) is backed up first.")
    if leftovers:
        names = [str(Path(p).relative_to(folder)) for p in leftovers]
        shown = "\n".join(f"  {n}" for n in names[:SHOWN_LEFTOVERS])
        more = f"\n  ...and {len(names) - SHOWN_LEFTOVERS} more" if len(names) > SHOWN_LEFTOVERS else ""
        text += (f" Leftover files from an earlier village in Save {target} are kept in "
                 f"Backups\\Replaced by copy {_stamp(when)}.\n\n{shown}{more}\n\n")
    else:
        text += " "
    return text + "Copy it?"


def ask_yes_no(parent, title: str, message: str) -> bool:
    """Yes / No, No the default: Return and Escape (and closing the window) answer No, as only a click on
    Yes (or Space on it) says Yes."""
    top, answer = build_yes_no(parent, title, message)
    top.wait_window()
    return answer["yes"]


def build_yes_no(parent, title: str, message: str):
    """The question's window and its answer ({"yes": False} until Yes is chosen); `ask_yes_no` waits."""
    top = tk.Toplevel(parent)
    top.title(title)
    if parent is not None:
        top.transient(parent)
    answer = {"yes": False}
    frame = ttk.Frame(top, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=message, wraplength=560, justify="left").pack(anchor="w")
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e", pady=(12, 0))

    def say(yes: bool) -> None:
        answer["yes"] = yes
        top.destroy()

    yes = ttk.Button(buttons, text="Yes", command=lambda: say(True))
    no = ttk.Button(buttons, text="No", command=lambda: say(False), default="active")
    yes.pack(side="left")
    no.pack(side="left", padx=(8, 0))
    for key in ("<Return>", "<KP_Enter>", "<Escape>"):
        top.bind(key, lambda _event: say(False))
    top.protocol("WM_DELETE_WINDOW", lambda: say(False))
    top.yes_button, top.no_button = yes, no
    no.focus_set()
    try:
        top.grab_set()
    except tk.TclError:
        pass
    return top, answer


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
    now: datetime | None = None,
) -> vv_copy_slot.CopyResult | None:
    """Ask first -- the replace question for a slot that holds a player, the copy question (with every
    leftover file named) for an empty one; No is the default.  Only a Yes backs up and copies, and only the
    files named are set aside.  None when the player said No: then nothing at all was written."""
    when = now or datetime.now().replace(microsecond=0)
    files = vv_copy_slot.slot_files(game, folder, target)
    save = game.save_path(Path(folder), target)
    if save.is_file():
        try:
            old_name = vv_tribe_rename.save_name(game, save.read_bytes()) or "unreadable"
        except OSError:
            old_name = "unreadable"
        message = replace_text(folder, source, target, old_name, new_name, when)
    else:
        message = empty_text(folder, source, target, new_name, when, files)
    if not ask(parent, TITLE, message):
        return None
    return run(lambda: vv_copy_slot.copy_slot(game, folder, source.slot, target, new_name, processes=processes,
                                              now=when, expected_removals=files))


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
            "Copies a village into another slot of the same save folder, under a new name, with "
            "everything the patcher keeps for it (its logs and data). A slot is empty when the game has no "
            "save for it, whatever its slot list says. Copying over a slot that holds a player replaces "
            "that village: you are asked first. The game must be closed. The whole save folder is backed up "
            "first, into <save folder>\\Backups\\Backup <date and time> (before copy), and the files the "
            "copy replaces are kept in <save folder>\\Backups\\Replaced by copy <date and time>. The "
            "village you copy from is not changed."
        ),
        wraplength=560, justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    game_var = tk.StringVar(value=build.title if build is not None else titles[0])
    folder_var, source_var, target_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    name_var, counter_var, problem_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    state: dict = {"folders": [], "slots": None, "targets": []}

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

    def taken_names(target: int) -> set[str]:
        """The names the older shared logs keep an earlier village of ``target`` under (read once per
        folder and slot): the copy may not take one (vv_copy_slot.shared_log_names)."""
        folder = state["folders"][folder_box.current()]
        key = (str(folder), target)
        cache = state.setdefault("taken", {})
        if key not in cache:
            cache[key] = vv_copy_slot.shared_log_names(folder, target)
        return cache[key]

    def chosen():
        slots = state["slots"]
        if slots is None or not state["folders"]:
            return None, None
        s, t = source_box.current(), target_box.current()
        source = slots.sources[s] if 0 <= s < len(slots.sources) else None
        target = state["targets"][t] if 0 <= t < len(state["targets"]) else None
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
            problem = "This save folder has no player to copy (no slot has a save the game can load)."
        elif target is None:
            problem = "Choose the slot to copy to."
        elif name:
            problem = vv_tribe_rename.name_problem(saves, name)
            if problem is None and name in taken_names(target):
                problem = vv_copy_slot.name_taken_message(name, target)
        problem_var.set(problem or "")
        copy_button.configure(state="normal" if problem is None and name else "disabled")

    def load_targets(*_args) -> None:
        """Every slot but the source: an empty one, or the village it would overwrite."""
        slots = state["slots"]
        source = chosen()[0]
        state["targets"] = [s for s in vv_copy_slot.SLOTS if source is None or s != source.slot] if slots else []
        labels = [slots.label(s) for s in state["targets"]] if slots else []
        target_box.configure(values=labels)
        empty = next((n for n, s in enumerate(state["targets"]) if s in slots.targets), 0) if slots else 0
        if labels:
            target_box.current(empty)
        else:
            target_var.set("")
        refresh()

    def load_slots(*_args) -> None:
        index = folder_box.current()
        state["slots"] = None
        state["taken"] = {}
        if 0 <= index < len(state["folders"]):
            state["slots"] = vv_copy_slot.read_slots(game(), state["folders"][index])
        slots = state["slots"]
        sources = [info.label for info in slots.sources] if slots else []
        source_box.configure(values=sources)
        source_var.set(sources[0] if sources else "")
        if sources:
            source_box.current(0)
        load_targets()

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
                ask_yes_no,
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
        aside = (f"\n\nThe {len(result.removed)} file(s) Save {result.target} held before are kept in "
                 f"{result.set_aside}." if result.set_aside else "")
        messagebox.showinfo(
            TITLE,
            f"\"{result.old_name}\" (Save {result.source}) was copied to Save {result.target} as "
            f"\"{result.new_name}\" ({folder.name}).\n\n{len(result.created)} file(s) made and read back."
            f"{skipped}{aside}\n\nBackup: {result.backup.backup_folder}",
            parent=dialog,
        )
        name_var.set("")
        load_slots()

    copy_button.configure(command=start)
    game_box.bind("<<ComboboxSelected>>", load_folders)
    folder_box.bind("<<ComboboxSelected>>", load_slots)
    source_box.bind("<<ComboboxSelected>>", load_targets)
    target_box.bind("<<ComboboxSelected>>", refresh)
    name_var.trace_add("write", refresh)
    frame.columnconfigure(1, weight=1)
    load_folders()
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.update_idletasks()
    dialog.grab_set()
    name_entry.focus_set()
