"""The Copy Player Slot window (Tools tab): pick a game, its save folder, the village to copy, the slot to
copy it to and a name; confirm; then src/vv_copy_slot.py copies it off the main thread.

The owner: "All 'Copy Player Slot' should have a confirmation prompt too", then "I want the Copy Player
slot to be able to overwrite existing slots (with a confirmation prompt of course)".  "Copy to" lists every
slot but the source; a slot that holds a player says "(will be overwritten)" and gets its own question.
No is the default; Return and Escape answer No (`ask_yes_no`).  Answering No writes nothing, not even the
backup (`confirm_and_copy`).  The prompts' words are the ones every patcher shares.

Move (the owner, 2026-11-22: "transfer save files AND BACKUPS AND LOGS AND ALL DATA FILES TIED TO A SAVE SLOT
TO A DIFFERENT SLOT (CAN BE EXTRA DIALOGUES IN COPY PLAYER SLOT)"): the window's "Move" choice moves the
village, keeping its name, with every file of its slot (src/vv_move_slot.py).  A target that holds a player
gets the same replace question first; then every file that will move is listed (`ask_preview`), No the
default; only Yes backs up and moves (`confirm_and_move`).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import messagebox, ttk

import vv_copy_slot
import vv_delete_slot
import vv_move_slot
import vv_save_backup
import vv_tribe_rename

TITLE = "Copy Player Slot"
MOVE_TITLE = vv_move_slot.TITLE
DELETE_TITLE = vv_delete_slot.TITLE
# The most set-aside leftover files named one by one in the question; the rest are counted.
SHOWN_LEFTOVERS = 25


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H-%M-%S")


def _aside(when: datetime, slot: int) -> str:
    """The folder in Backups the replaced files go to (vv_copy_slot.set_aside_folder: a short name, the
    owner's 2026-11-20 "no path-too-long errors"; " 2" ... when that minute's is taken)."""
    return f"{when:%Y-%m-%d %H%M} S{slot}"


def replace_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, old_name: str, new_name: str,
                 when: datetime) -> str:
    """The question for a target slot that holds a player (the patchers' shared words)."""
    return (f"Save {target} holds the {old_name} village. It will be replaced by a copy of {source.name} "
            f"(Save {source.slot}), named {new_name}. The whole save folder ({folder}) is backed up first, and "
            f"{old_name}'s files are kept in Backups\\{_aside(when, target)}. Replace it?")


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
                 f"Backups\\{_aside(when, target)}.\n\n{shown}{more}\n\n")
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


def move_replace_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, old_name: str,
                      when: datetime) -> str:
    """The question for a move into a slot that holds a player (the patchers' shared words)."""
    return (f"Save {target} holds the {old_name} village. It will be replaced by {source.name}, moved from "
            f"Save {source.slot} with all its files. The whole save folder ({folder}) is backed up first, and "
            f"{old_name}'s files are kept in Backups\\{_aside(when, target)}. Replace it?")


def move_text(folder: Path, source: vv_tribe_rename.SlotInfo, target: int, plan: vv_move_slot.Plan,
              when: datetime) -> str:
    """The move's own question, above the list of every file (the patchers' shared words)."""
    text = (f"{source.name} will move from Save {source.slot} to Save {target}, keeping its name, with its "
            f"save, the game's older copies of it, its logs, data, family trees and repair copies. Save "
            f"{source.slot} will be empty. The whole save folder ({folder}) is backed up first.")
    if plan.removals:
        whose = "Leftover files from an earlier village" if plan.overwritten is None else "The files"
        text += f" {whose} in Save {target} are kept in Backups\\{_aside(when, target)}."
    count = len(plan.moves) + len(plan.files)
    return text + f"\n\nEverything that will change ({count} file(s) moved or made):"


def preview_lines(plan: vv_move_slot.Plan, when: datetime) -> list[str]:
    """The list under the question: each file moved (old -> new), then each file set aside."""
    lines = plan.preview()
    for path in plan.removals:
        lines.append(f"Kept in Backups\\{_aside(when, plan.target)}:  {Path(path).relative_to(plan.folder)}")
    return lines


def ask_preview(parent, title: str, message: str, lines: list[str], question: str = "Move it?") -> bool:
    """Yes / No under a scrolled list of every change; No the default (Return, Escape and closing say No)."""
    top, answer = build_preview(parent, title, message, lines, question)
    top.wait_window()
    return answer["yes"]


def build_preview(parent, title: str, message: str, lines: list[str], question: str = "Move it?"):
    """The preview window and its answer ({"yes": False} until Yes is chosen); `ask_preview` waits."""
    top = tk.Toplevel(parent)
    top.title(title)
    if parent is not None:
        top.transient(parent)
    answer = {"yes": False}
    frame = ttk.Frame(top, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=message, wraplength=640, justify="left").pack(anchor="w")
    box = ttk.Frame(frame)
    box.pack(fill="both", expand=True, pady=(8, 0))
    listing = tk.Text(box, width=96, height=16, wrap="none", font="TkDefaultFont")
    down = ttk.Scrollbar(box, orient="vertical", command=listing.yview)
    across = ttk.Scrollbar(box, orient="horizontal", command=listing.xview)
    listing.configure(yscrollcommand=down.set, xscrollcommand=across.set)
    listing.grid(row=0, column=0, sticky="nsew")
    down.grid(row=0, column=1, sticky="ns")
    across.grid(row=1, column=0, sticky="we")
    box.rowconfigure(0, weight=1)
    box.columnconfigure(0, weight=1)
    listing.insert("1.0", "\n".join(lines))
    listing.configure(state="disabled")
    ttk.Label(frame, text=question).pack(anchor="w", pady=(8, 0))
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
    top.yes_button, top.no_button, top.listing = yes, no, listing
    no.focus_set()
    try:
        top.grab_set()
    except tk.TclError:
        pass
    return top, answer


def delete_text(folder: Path, plan: vv_delete_slot.Plan) -> str:
    """The delete's question above the list of every file (the patchers' shared words)."""
    village = plan.name or "an unreadable village"
    backups = sum(1 for g in plan.groups if g.where and g.aside is None)
    asides = sum(1 for g in plan.groups if g.aside is not None)
    text = (f"Every file of Save {plan.slot} ({village}) goes to the Recycle Bin: its save, the game's older copies "
            f"of it, its logs, data, family trees and repair copies, and its files in {backups} backup(s)")
    text += f" and {asides} folder(s) of files it replaced." if asides else "."
    text += (f" Pictures stay where they are. Other slots are not touched. No new backup is made: anything can be "
             f"put back from the Recycle Bin. ({folder})")
    return text + f"\n\n{len(plan.files)} file(s) to the Recycle Bin, {len(plan.pictures)} picture(s) kept:"


def delete_final_text(plan: vv_delete_slot.Plan) -> str:
    """The second, explicit question, naming the village."""
    village = plan.name or "the unreadable village"
    return (f"Delete {village} from Save {plan.slot}? Its {len(plan.files)} file(s), in this save folder and in "
            "its backups, go to the Recycle Bin. Delete it?")


def confirm_and_delete(
    ask: Callable[..., bool],
    preview: Callable[..., bool],
    run: Callable[[Callable[[], vv_delete_slot.DeleteResult]], vv_delete_slot.DeleteResult],
    game: vv_tribe_rename.GameSaves,
    folder: Path,
    source: vv_tribe_rename.SlotInfo,
    parent=None,
    processes=None,
    now: datetime | None = None,
    recycle=None,
) -> vv_delete_slot.DeleteResult | None:
    """Refused at once while the game runs.  Every file is listed first; then a second question names the
    village.  Only Yes to both sends exactly what was listed to the Recycle Bin.  None when the player said
    No: then nothing at all changed."""
    vv_delete_slot._refuse_if_running(Path(folder), processes if processes is not None
                                      else vv_save_backup.WindowsProcesses())
    plan = vv_delete_slot.plan_delete(game, folder, source.slot)
    if not preview(parent, DELETE_TITLE, delete_text(folder, plan), plan.preview(), "Delete it?"):
        return None
    if not ask(parent, DELETE_TITLE, delete_final_text(plan)):
        return None
    shown = plan.signature()
    return run(lambda: vv_delete_slot.delete_slot(game, folder, source.slot, processes=processes, now=now,
                                                  expected=shown, recycle=recycle))


def confirm_and_move(
    ask: Callable[..., bool],
    preview: Callable[..., bool],
    run: Callable[[Callable[[], vv_move_slot.MoveResult]], vv_move_slot.MoveResult],
    game: vv_tribe_rename.GameSaves,
    folder: Path,
    source: vv_tribe_rename.SlotInfo,
    target: int,
    parent=None,
    processes=None,
    now: datetime | None = None,
) -> vv_move_slot.MoveResult | None:
    """Refused at once while the game runs.  A target that holds a player gets the replace question first;
    then the move's question over the list of every file.  Only Yes to both backs up and moves exactly what
    was listed.  None when the player said No: then nothing at all was written."""
    when = now or datetime.now().replace(microsecond=0)
    vv_move_slot._refuse_if_running(Path(folder), processes if processes is not None
                                    else vv_save_backup.WindowsProcesses())
    plan = vv_move_slot.plan_move(game, folder, source.slot, target)
    if plan.overwritten is not None:
        if not ask(parent, MOVE_TITLE, move_replace_text(folder, source, target, plan.overwritten or "unreadable", when)):
            return None
    if not preview(parent, MOVE_TITLE, move_text(folder, source, target, plan, when), preview_lines(plan, when)):
        return None
    shown = plan.signature()
    return run(lambda: vv_move_slot.move_slot(game, folder, source.slot, target, processes=processes, now=when,
                                              expected=shown))


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
            "first, into <save folder>\\Backups\\<date and time> (listed as \"before copy\"), and the files "
            "the copy replaces are kept in <save folder>\\Backups\\<date and time> S<slot>. The "
            "village you copy from is not changed.\n\n"
            "Move instead takes the village itself, keeping its name, to the other slot with everything "
            "tied to its slot -- its save and the game's older copies of it, its logs, data, family trees "
            "and repair copies -- and leaves its slot empty. You see every file before saying Yes; the "
            "folder is backed up first (listed as \"before move\").\n\n"
            "Delete sends every file of a slot -- its save, logs, data, family trees, repair copies and its "
            "files inside every backup -- to the Recycle Bin, where it can be put back. Pictures stay. You "
            "see every file and are asked twice."
        ),
        wraplength=560, justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    game_var = tk.StringVar(value=build.title if build is not None else titles[0])
    folder_var, source_var, target_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    name_var, counter_var, problem_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    mode_var = tk.StringVar(value="copy")
    state: dict = {"folders": [], "slots": None, "targets": []}

    ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w")
    game_box = ttk.Combobox(frame, textvariable=game_var, values=titles, state="readonly", width=48)
    game_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="Save folder:").grid(row=2, column=0, sticky="w")
    folder_box = ttk.Combobox(frame, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=2, column=1, columnspan=2, sticky="we", pady=2)
    ttk.Label(frame, text="Do:").grid(row=3, column=0, sticky="w")
    modes = ttk.Frame(frame)
    modes.grid(row=3, column=1, columnspan=2, sticky="w", pady=2)
    copy_choice = ttk.Radiobutton(modes, text="Copy (a second village, under a new name)", value="copy",
                                  variable=mode_var)
    copy_choice.pack(anchor="w")
    move_choice = ttk.Radiobutton(modes, text="Move (the same village and all its files; its slot is left empty)",
                                  value="move", variable=mode_var)
    move_choice.pack(anchor="w")
    delete_choice = ttk.Radiobutton(modes, text="Delete (every file of the slot to the Recycle Bin; pictures stay)",
                                    value="delete", variable=mode_var)
    delete_choice.pack(anchor="w")
    from_label = ttk.Label(frame, text="Copy from:")
    from_label.grid(row=4, column=0, sticky="w")
    source_box = ttk.Combobox(frame, textvariable=source_var, state="readonly", width=48)
    source_box.grid(row=4, column=1, columnspan=2, sticky="we", pady=2)
    to_label = ttk.Label(frame, text="Copy to:")
    to_label.grid(row=5, column=0, sticky="w")
    target_box = ttk.Combobox(frame, textvariable=target_var, state="readonly", width=48)
    target_box.grid(row=5, column=1, columnspan=2, sticky="we", pady=2)
    name_label = ttk.Label(frame, text="New name:")
    name_label.grid(row=6, column=0, sticky="w", pady=(8, 0))
    name_entry = ttk.Entry(frame, textvariable=name_var, width=36)
    name_entry.grid(row=6, column=1, sticky="w", pady=(8, 0))
    counter = ttk.Label(frame, textvariable=counter_var)
    counter.grid(row=6, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=560, justify="left").grid(
        row=7, column=0, columnspan=3, sticky="w", pady=(4, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 0))
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

    def moving() -> bool:
        return mode_var.get() == "move"

    def deleting() -> bool:
        return mode_var.get() == "delete"

    def refresh(*_args) -> None:
        saves = game()
        move, delete = moving(), deleting()
        verb = "delete" if delete else "move" if move else "copy"
        name = name_var.get()
        from_label.configure(text="Delete:" if delete else "Move from:" if move else "Copy from:")
        to_label.configure(text="" if delete else "Move to:" if move else "Copy to:")
        target_box.configure(state="disabled" if delete else "readonly")
        name_entry.configure(state="disabled" if move or delete else "normal")
        counter_var.set("" if delete else "(the village keeps its name)" if move
                        else f"{len(name)} / {saves.max_length} characters")
        counter.configure(foreground="#a01010" if not (move or delete) and len(name) > saves.max_length else "")
        copy_button.configure(text=verb.capitalize() + "...")
        source, target = chosen()
        problem = None
        if not state["folders"]:
            problem = "No save folder was found for this game."
        elif source is None:
            problem = f"This save folder has no player to {verb} (no slot has a save the game can load)."
        elif delete:
            pass
        elif target is None:
            problem = "Choose the slot to " + ("move" if move else "copy") + " to."
        elif move:
            if source.name in taken_names(target):
                problem = vv_move_slot.taken_message(source.name, target)
        elif name:
            problem = vv_tribe_rename.name_problem(saves, name)
            if problem is None and name in taken_names(target):
                problem = vv_copy_slot.name_taken_message(name, target)
        problem_var.set(problem or "")
        copy_button.configure(state="normal" if problem is None and (name or move or delete) else "disabled")

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

    def start_move(source, target, folder, saves) -> None:
        try:
            result = confirm_and_move(
                ask_yes_no, ask_preview,
                lambda work: app._run_with_wait("Moving the slot…\n\nThe save folder is backed up first.", work),
                saves, folder, source, target, parent=dialog)
        except (vv_copy_slot.CopyError, vv_save_backup.BackupError, OSError) as exc:
            _regrab(dialog)
            app.status_var.set("Move Player Slot: nothing was moved.")
            messagebox.showerror(MOVE_TITLE, str(exc), parent=dialog)
            load_slots()
            return
        _regrab(dialog)
        if result is None:
            app.status_var.set("Move Player Slot: nothing was moved.")
            return
        app.status_var.set(f"Move Player Slot: {result.name} moved from Save {result.source} to Save {result.target}.")
        aside = (f"\n\nThe {len(result.removed)} file(s) Save {result.target} held before are kept in "
                 f"{result.set_aside}." if result.set_aside else "")
        notes = ("\n\n" + "\n".join(result.notes)) if result.notes else ""
        messagebox.showinfo(
            MOVE_TITLE,
            f"\"{result.name}\" was moved from Save {result.source} to Save {result.target} ({folder.name}), "
            f"with {len(result.moved)} file(s); {len(result.updated)} of them now name Save {result.target} "
            f"inside. Save {result.source} is empty. Every file was read back. The Repairs log of Save "
            f"{result.target} lists every file moved.{aside}{notes}\n\nBackup: {result.backup.backup_folder}",
            parent=dialog,
        )
        load_slots()

    def start_delete(source, folder, saves) -> None:
        try:
            result = confirm_and_delete(
                ask_yes_no, ask_preview,
                lambda work: app._run_with_wait("Sending the slot's files to the Recycle Bin…", work),
                saves, folder, source, parent=dialog)
        except (vv_copy_slot.CopyError, vv_save_backup.BackupError, OSError) as exc:
            _regrab(dialog)
            app.status_var.set("Delete Player Slot: nothing was deleted.")
            messagebox.showerror(DELETE_TITLE, str(exc), parent=dialog)
            load_slots()
            return
        _regrab(dialog)
        if result is None:
            app.status_var.set("Delete Player Slot: nothing was deleted.")
            return
        notes = ("\n\n" + "\n".join(result.notes)) if result.notes else ""
        kept = f" {len(result.pictures)} picture(s) were kept." if result.pictures else ""
        if result.problem is None:
            app.status_var.set(f"Delete Player Slot: Save {result.slot} sent to the Recycle Bin.")
            messagebox.showinfo(
                DELETE_TITLE,
                f"Save {result.slot} ({result.name or 'unreadable'}) was deleted: {len(result.recycled)} file(s), "
                f"from this save folder and {result.backups_touched} backup(s), are in the Recycle Bin, where they "
                f"can be put back.{kept}{notes}", parent=dialog)
        else:
            app.status_var.set(f"Delete Player Slot: Save {result.slot} was only partly deleted.")
            left = "\n".join(f"  {p.relative_to(folder)}" for p in result.not_recycled[:25])
            more = f"\n  ...and {len(result.not_recycled) - 25} more" if len(result.not_recycled) > 25 else ""
            messagebox.showerror(
                DELETE_TITLE,
                f"{result.problem} {len(result.recycled)} file(s) are in the Recycle Bin; "
                f"{len(result.not_recycled)} are still here:\n\n{left}{more}{notes}", parent=dialog)
        load_slots()

    def start() -> None:
        source, target = chosen()
        if source is None:
            return
        folder = state["folders"][folder_box.current()]
        saves = game()
        if deleting():
            start_delete(source, folder, saves)
            return
        if target is None:
            return
        if moving():
            start_move(source, target, folder, saves)
            return
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
    mode_var.trace_add("write", refresh)
    frame.columnconfigure(1, weight=1)
    load_folders()
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.update_idletasks()
    dialog.grab_set()
    name_entry.focus_set()
