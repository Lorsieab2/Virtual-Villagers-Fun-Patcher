"""Sideways scroll bars for the patcher's windows (the owner, 2026-11-11: "i wanted the
sideways scrolling and vertical scrolling everywhere in the patcher").

Every scrolling area already has its vertical bar. horizontal_bar() gives one a horizontal bar
under it as well. The bar shows only while the content is wider than its box, so a window whose
content fits looks exactly as it did before; it appears as soon as something is cut off at the
side, and Shift + the mouse wheel scrolls the same way. scrolled_listbox() makes a list (the
tribe pickers) with both bars, each shown only while needed.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

SHIFT = 0x0001                                  # the Shift bit of a Tk event's state


def shifted(event) -> bool:
    """True when Shift is held: the wheel then scrolls sideways."""
    try:
        return bool(int(event.state) & SHIFT)
    except (AttributeError, TypeError, ValueError):
        return False


class AutoScrollbar(ttk.Scrollbar):
    """A scroll bar (horizontal unless told otherwise) that is on screen only while there is
    something to scroll."""

    def __init__(self, master, show, hide, orient: str = "horizontal", **options) -> None:
        super().__init__(master, orient=orient, **options)
        self._show, self._hide = show, hide
        self.shown = False

    def set(self, first, last) -> None:                          # noqa: A003 (Tk's name)
        needed = float(first) > 0.0 or float(last) < 1.0
        if needed != self.shown:
            self.shown = needed
            try:
                (self._show if needed else self._hide)(self)
            except tk.TclError:
                pass                                            # the window is closing
        super().set(first, last)


def horizontal_bar(widget: tk.Widget) -> AutoScrollbar:
    """A horizontal scroll bar for an already placed Text, Canvas, Listbox or Treeview, put
    straight under it in the same container (pack or grid). It shows only while needed."""
    manager = widget.winfo_manager()
    if manager == "pack":
        info = widget.pack_info()
        container = info["in"]

        def show(bar) -> None:
            bar.pack(in_=container, side="bottom", fill="x", before=widget)
    elif manager == "grid":
        info = widget.grid_info()
        container = info["in"]
        row = int(info["row"]) + int(info.get("rowspan", 1))
        column, span = int(info["column"]), int(info.get("columnspan", 1))
        if container.grid_slaves(row=row, column=column):
            raise ValueError(f"grid row {row} under {widget} is taken")

        def show(bar) -> None:
            bar.grid(in_=container, row=row, column=column, columnspan=span, sticky="ew")
    else:
        raise ValueError(f"{widget} is not packed or gridded ({manager!r})")

    def hide(bar) -> None:
        bar.pack_forget() if manager == "pack" else bar.grid_remove()

    bar = AutoScrollbar(widget.master, show, hide, command=widget.xview)
    widget.configure(xscrollcommand=bar.set)
    return bar


def scrolled_listbox(parent, **options) -> tuple[ttk.Frame, tk.Listbox]:
    """A Listbox in a frame of its own (placed by the caller), with a vertical and a horizontal
    scroll bar, each shown only while the list is taller or wider than its box."""
    holder = ttk.Frame(parent)
    listbox = tk.Listbox(holder, **options)
    listbox.pack(side="left", fill="both", expand=True)

    def show(bar) -> None:
        bar.pack(side="right", fill="y", before=listbox)

    bar = AutoScrollbar(holder, show, lambda bar: bar.pack_forget(), orient="vertical",
                        command=listbox.yview)
    listbox.configure(yscrollcommand=bar.set)
    horizontal_bar(listbox)
    return holder, listbox


def page_width(width: int, wanted: int, least: int | None = None) -> int:
    """The width a scrolling page is laid out at in a canvas `width` wide: the canvas's own width,
    unless that is narrower than the page needs. The page needs its requested width (`wanted`), or,
    with `least` (the canvas's width at the window's usual size), no more than that: a label that
    wraps to its box, or a row that flows onto more lines, asks for its whole unwrapped width, yet
    fits the usual size, so it still wraps there exactly as before. Only a canvas made narrower than
    the page needs keeps the page at that width, and its horizontal bar reaches the rest."""
    need = wanted if least is None else min(wanted, least)
    return max(width, need)


def fill_or_keep_width(canvas: tk.Canvas, item, inner: tk.Widget, least: int | None = None) -> None:
    """A canvas window item that fills its canvas; in a canvas narrower than the frame needs
    (page_width), the frame keeps that width and the canvas scrolls sideways to it, instead of
    the frame being squeezed and its right side cut off."""

    def fit(_event=None) -> None:
        try:
            wanted = page_width(canvas.winfo_width(), inner.winfo_reqwidth(), least)
            if str(canvas.itemcget(item, "width")) != str(wanted):
                canvas.itemconfigure(item, width=wanted)
            canvas.configure(scrollregion=canvas.bbox("all"))
        except tk.TclError:
            pass                                                # the window is closing

    inner.bind("<Configure>", fit, add="+")
    canvas.bind("<Configure>", fit, add="+")


def scroll_sideways(widget, event) -> None:
    """Shift + wheel over a canvas (or the window's page) moves it sideways."""
    widget.xview_scroll(-1 if event.delta > 0 else 1, "units")
