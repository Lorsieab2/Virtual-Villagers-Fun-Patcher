"""The read-only reconciliation, run whenever a patcher window opens a village (src/vv_reconcile.py).

Every tribe picker (Check Saves & Logs, Repair Saves & Logs, Rename Tribe, the Family Tree Maker and
the other village windows) calls `watch` when a tribe is chosen: the reconciliation runs off the
window's thread, its one-line summary appears in the picker, and its report is written to the save's
own "Virtual Villagers Fun Patcher\\Save <n>\\Logs\\Reconciliation" folder (an older save's
"...Logs\\Save <n>\\Reconciliation" while it is written there) -- except by Check Saves & Logs and Repair
Saves & Logs' picker, which only read (`export=False`; Repair writes it once Repair is pressed).  It never
changes the save, a log or a data file.
"""
from __future__ import annotations

import struct
import threading
import tkinter as tk
from pathlib import Path

import vv_reconcile

WAITING = "Reconciling this village's records, logs and files (read-only)..."


def watch(widget, var, folder: Path, game: int, slot: int, on_done=None, export: bool = True) -> None:
    """Reconcile (folder, game, slot) in the background and show the summary in `var` (a Tk variable
    owned by `widget`).  Choosing the same village again does not run it twice; choosing another one
    while it runs drops the first result.  `export` False: the report is not written (Check Saves & Logs
    and Repair Saves & Logs' picker only read; Repair writes it when Repair is pressed)."""
    key = (str(folder), game, slot)
    if getattr(widget, "_vv_reconcile_key", None) == key:
        return
    widget._vv_reconcile_key = key
    var.set(WAITING)
    box: dict = {}

    def work() -> None:
        try:
            rec = vv_reconcile.reconcile(Path(folder), game, slot)
        except (vv_reconcile.ReconcileError, OSError, ValueError, KeyError, IndexError, struct.error) as exc:
            box["error"] = exc
            return
        if export:
            try:
                box["path"] = vv_reconcile.export(rec)
            except OSError as exc:
                box["export_error"] = exc
        box["result"] = rec

    thread = threading.Thread(target=work, name="vvfp-reconcile", daemon=True)
    thread.start()

    def poll() -> None:
        if getattr(widget, "_vv_reconcile_key", None) != key:
            return                              # another village was chosen meanwhile
        if thread.is_alive():
            try:
                widget.after(150, poll)
            except tk.TclError:                 # the window closed meanwhile
                pass
            return
        if "error" in box:
            var.set(f"Reconciliation: could not run ({box['error']}). Nothing was changed.")
            return
        rec = box["result"]
        text = rec.summary()
        if "path" in box:
            try:                                # the save's own folder, or an older save's "...Logs\Save <n>"
                where = Path(box["path"]).relative_to(Path(folder))
            except ValueError:
                where = Path(box["path"]).name
            text += f" Report: {where}."
        elif "export_error" in box:
            text += f" (The report could not be written: {box['export_error']}.)"
        try:
            var.set(text)
        except tk.TclError:
            return
        if on_done is not None:
            on_done(rec)

    try:
        widget.after(150, poll)
    except tk.TclError:                         # the window closed before the first poll: nothing to show
        pass


def forget(widget) -> None:
    """No village chosen: the next choice runs again."""
    widget._vv_reconcile_key = None
