"""The Family Tree Maker's Villager Info tab (the owner, 2026-10-10: "The selected villager portrait
shows vital information like: Icon, name, age, partners, list of children and babies on the way with
each partner, any other special notes.  males should have bolded blue names and ages and females
should have bolded pink names and ages").

Read-only: it shows what the village model (vv_genealogy) and the tree's edits say, and changes
neither.  `info_lines` builds the words (tested on its own); `VillagerInfoTab` shows them in the
editor's side panel, follows the selection, and selects a partner or child clicked by name.
"""
from __future__ import annotations

import struct
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import vv_family_tree as ft
import vv_genealogy as gen

# Coloured by sex (not bold: the owner found bold pink and blue hard on the eyes), readable on the
# panel's light grey (contrast 5:1 or better on #f0f0f0).
MALE = "#1f5fbf"
FEMALE = "#c2185b"
UNKNOWN = "#666666"                     # a baby on the way, or anyone whose sex no record gives
HINT = "Select one villager to see their information."
TAB_NAME = "Villager Info"
ICON_ZOOM = 3                           # the head sprite at three times its size: readable in the panel

Run = tuple                             # (text, style, pid or None): style "plain", "heading", "note",
                                        # "Male", "Female" or "unknown" (bold, coloured by sex)


def _sex_style(p: gen.Person) -> str:
    return p.sex if p.sex in ("Male", "Female") and not p.upcoming else "unknown"


def shown_name(names: dict, p: gen.Person) -> str:
    """The name as the tree shows it (Number Duplicate Names' numeral too)."""
    if p.upcoming:
        return "Upcoming child"
    return names.get(p.id, p.name) or "(unnamed)"


def age_words(edits: ft.Edits, p: gen.Person) -> str:
    """The age in the tree's own wording: game units and/or years as the portrait's group shows them
    (years alone when the tree shows neither).  0 is a real age."""
    if p.upcoming:
        return "on the way"
    if p.age is None:
        return "age unknown"
    units, years = ft.opt(edits, p, "show_units"), ft.opt(edits, p, "show_years")
    if not units and not years:
        years = True
    text = " / ".join(([f"{p.age} game units"] if units else []) + ([f"{p.years} years old"] if years else []))
    return f"died at {text}" if p.gone == "died" else text


def _person_runs(edits: ft.Edits, names: dict, p: gen.Person, link: bool = True) -> list[Run]:
    style = _sex_style(p)
    return [(shown_name(names, p), style, p.id if link and not p.upcoming else None), (", ", "plain", None),
            (age_words(edits, p), style, None)] + ([] if p.gone == "died" and p.age is not None else _status_runs(p))


def _status_runs(p: gen.Person) -> list[Run]:
    if p.upcoming or p.alive:
        return [(" (Heathen)", "note", None)] if p.heathen else []
    return [(" " + _status(p), "note", None)]


def _status(p: gen.Person) -> str:
    return {"died": "(deceased)", "disappeared": "(disappeared)"}.get(p.gone, "(left the village)")


def _litter_words(n: int) -> str:
    return {1: "1 baby", 2: "twins", 3: "triplets"}.get(n, f"{n} babies")


def _born_order(p: gen.Person) -> tuple:
    """In order of birth: those born before the Births log began oldest first, then the logged births
    in the log's order (it is written as they are born), the babies on the way last.  (A dead child's age
    is their age at death, so age alone cannot order them once the log has them.)"""
    logged = p.birth_record is not None
    return (p.upcoming, logged, p.birth_record if logged else 0, -(p.age or 0), p.name)


def info_lines(village: gen.Village, edits: ft.Edits, pid: int, names: dict | None = None,
               titles: dict | None = None) -> list[list[Run]]:
    """The tab's lines for one villager, each a list of runs.  The first line is their name, the
    second their age; then their partners with their children and babies on the way together, the
    children whose other parent is unknown, and the notes that apply.  `titles` is village_titles'."""
    names = names or {}
    people = village.people
    p = people[pid]
    style = _sex_style(p)
    lines: list[list[Run]] = [[(shown_name(names, p), style, None)],
                              [(age_words(edits, p), style, None)]]
    if p.sex in ("Male", "Female") and not p.upcoming:
        lines.append([(p.sex, "plain", None)])

    # Partners: the other parent of each child, in the order of their first child's birth.
    groups: dict[int | None, list[gen.Person]] = {}
    for kid in sorted(village.children_of(pid), key=_born_order):
        other = kid.mother if kid.father == pid else kid.father
        groups.setdefault(other, []).append(kid)
    partners = [q for q in groups if q is not None and q in people]
    lines.append([])
    lines.append([("Partners", "heading", None)])
    if not partners:
        lines.append([("None recorded", "note", None)])
    for q in partners:
        partner = people[q]
        runs = _person_runs(edits, names, partner)
        runs[0] = (runs[0][0], runs[0][1] + "+strong", runs[0][2])     # the partner's name in bold
        lines.append([("", "plain", None)] + runs)
        lines.extend(_children_lines(village, edits, names, p, partner, groups[q]))
    if None in groups:
        lines.append([])
        lines.append([("Other parent unknown", "heading", None)])
        lines.extend(_children_lines(village, edits, names, p, None, groups[None]))

    notes = _notes(village, edits, names, p, titles)
    if notes:
        lines.append([])
        lines.append([("Notes", "heading", None)])
        lines.extend(notes)
    return lines


def _children_lines(village, edits, names, p, partner, kids) -> list[list[Run]]:
    out: list[list[Run]] = []
    born = [k for k in kids if not k.upcoming]
    coming = [k for k in kids if k.upcoming]
    if born:
        out.append([("    Children (in order of birth):", "note+strong", None)])
        for k in born:
            out.append([("      ", "plain", None)] + _person_runs(edits, names, k))
    if coming:
        litters: dict = {}
        for k in coming:
            litters.setdefault(k.litter if k.litter is not None else ("one", k.id), []).append(k)
        for babies in litters.values():
            row: list[Run] = [("      ", "plain", None),
                              (f"On the way: {_litter_words(len(babies))}", "unknown", None)]
            if partner is None:
                role = "father" if babies[0].mother == p.id else "mother"
                row.append((f" ({role} not known yet)", "note", None))
            else:
                role = "father" if partner.id == babies[0].father else "mother"
                row += [(f" (expected {role}: ", "note", None),
                        (shown_name(names, partner), _sex_style(partner), partner.id), (")", "note", None)]
            out.append(row)
    return out


def _notes(village: gen.Village, edits: ft.Edits, names: dict, p: gen.Person,
           titles: dict | None = None) -> list[list[Run]]:
    people = village.people
    out: list[list[Run]] = []

    def note(*runs: Run) -> None:
        out.append([("    ", "plain", None)] + list(runs))

    entry = edits.entries.get(ft.entry_key(village, p), {})
    if p.upcoming:
        note(("A baby on the way: not born yet", "plain", None))
    elif p.father is None and p.mother is None:
        first = min(gen.snapshot_dates(village), default=None)
        if gen.is_arrival(p, first):
            how = p.how if p.how and p.how.casefold() != "unknown" else ""
            note((f"Arrived: {how}" if how else "Arrived after the village began (how is not recorded)",
                  "plain", None))
        else:
            note(("Founder", "plain", None))
    if village.game == 1 and (p.family == 199 or p.how == "Golden Child"):
        note(("Golden Child (5 years old for life)", "plain", None))
    if p.heathen:
        note(("Heathen (not one of the tribe)", "plain", None))
    own = titles_of(village, titles or {}, p)
    if own.get("custom"):
        note((f"Custom title: {own['custom']}", "plain", None))
    special = own.get("special")
    golden = village.game == 1 and (p.family == 199 or p.how == "Golden Child")
    if special and not (golden and special == "Golden Child"):     # the Golden Child line above says it
        note((f"Special title: {special}", "plain", None))
    if entry.get("mark"):
        note((f"Special mark: {entry['mark']}", "plain", None))
    if p.litter is not None and not p.upcoming:
        others = sorted((q for q in people.values() if q.litter == p.litter and q.id != p.id and not q.upcoming),
                        key=_born_order)
        if others:
            runs: list[Run] = []
            for k, q in enumerate(others):
                if k:
                    runs.append((" and ", "plain", None))
                runs.append((shown_name(names, q), _sex_style(q), q.id))
            runs.append((f"'s {'twin' if len(others) == 1 else 'triplet'}", "plain", None))
            note(*runs)
    if not p.alive and not p.upcoming:
        note((_status(p).strip("()").capitalize(), "plain", None))
    for label, q in (("Father", p.father), ("Mother", p.mother)):
        if q is not None and q in people:
            note((f"{label}: ", "plain", None), *_person_runs(edits, names, people[q]))
    if not p.upcoming:
        number = f", number {p.number}" if p.number is not None else ""
        note((f"Generation {gen.roman(p.generation)}{number}", "plain", None))
    lost = getattr(p, "lost_before_birth", None)
    if lost:
        note((f"Lost before birth: {lost}", "plain", None))
    return out


# ---------------------------------------------------------------------------
# Titles: the player's Custom title and the game's Special villager title
# ---------------------------------------------------------------------------

TITLES_FILE = "Virtual Villagers Fun Patcher Data\\Custom Titles\\Custom Titles - Save {slot}.dat"


def read_titles_file(path: Path, game: int) -> list[tuple[int, int, str]]:
    """native/shared/custom_titles.h: (record index, identity, title) for each entry of a v2 file for
    this game; nothing for a missing, older or damaged one."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if len(data) < 16 or data[:4] != b"VCT1" or struct.unpack_from("<III", data, 4)[:2] != (2, game):
        return []
    count = struct.unpack_from("<I", data, 12)[0]
    if len(data) != 16 + 40 * count:
        return []
    out = []
    for k in range(count):
        index, identity = struct.unpack_from("<II", data, 16 + 40 * k)
        title = data[24 + 40 * k:56 + 40 * k].split(b"\0", 1)[0].decode("ascii", "replace").strip()
        if title:
            out.append((index, identity, title))
    return out


def file_titles(folder: Path, game: int, slot: int) -> dict[tuple, str] | None:
    """Each villager the save holds with a Custom title in the titles file, by (name, head, body):
    the entry's identity (the name, likes and dislikes -- vv_title_identity) is that villager's, as
    the game's load matches it.  An identity two villagers share is nobody's.  None when the file
    or the save cannot be read (the logs then say)."""
    import vv_last_names as ln
    import vv_save_layout as layout
    path = layout.find(Path(folder), TITLES_FILE.format(slot=slot))
    if not path.is_file():
        return None
    entries = read_titles_file(path, game)
    try:
        data = ln.save_path(folder, game, slot).read_bytes()
        held = ln.living(folder, game, slot, bodies=True)
    except (OSError, ln.LastNamesError, ValueError):
        return None
    f = ln.FIELDS[game]
    by_identity: dict[int, list[tuple]] = {}
    for v in held:
        by_identity.setdefault(ln._title_identity(data, v.at, f), []).append(v.identity)
    out = {}
    for _index, identity, title in entries:
        owners = by_identity.get(identity, [])
        if len(owners) == 1:
            out[owners[0]] = title
    # Everyone the save holds is decided by the file: no entry, no title.
    return {v.identity: out.get(v.identity, "") for v in held}


def log_titles(folder: Path, game: int, slot: int) -> dict[tuple, dict]:
    """Each villager's Custom title and Special villager title as their latest record says: the
    Village Population page, then the History snapshots newest first, then the other records."""
    import vv_log_additions as additions
    try:
        blocks = additions.person_blocks(Path(folder), slot, game)
    except (OSError, ValueError):
        return {}
    try:
        population = list(additions.population_page(Path(folder), slot, game)[1].values())     # the latest page
    except (OSError, ValueError):
        population = []
    history = sorted((b for b in blocks if not additions.is_population(b.path) and b.date
                      and b.heading.startswith("Villager ")), key=lambda b: b.date, reverse=True)
    taken = {id(b) for b in history}
    rest = [b for b in reversed(blocks) if id(b) not in taken and not additions.is_population(b.path)]
    out: dict[tuple, dict] = {}
    for b in population + history + rest:
        name, head, body = b.identity
        if not name or head is None or body is None:
            continue
        got = out.setdefault((name, head, body), {})
        for key, label in (("custom", "Custom title"), ("special", "Special villager")):
            value = b.value(label)
            if key not in got and value is not None:
                got[key] = "" if value.strip().lower() in ("", "none", "-") else value.strip()
    return out


def village_titles(folder: Path, game: int, slot: int) -> dict[tuple, dict]:
    """Every villager's titles by (name, head, body) -- 0 a real head and body: the Custom title from
    the save folder's Custom Titles file for the villagers the save holds, else their latest record's;
    the Special villager title from the latest record."""
    out = log_titles(folder, game, slot)
    held = file_titles(folder, game, slot)
    for key, title in (held or {}).items():
        out.setdefault(key, {})["custom"] = title
    return out


def titles_of(village: gen.Village, titles: dict, p: gen.Person) -> dict:
    """One villager's titles, found by their key now, the keys of their earlier looks (Change
    Appearance) or of the cut name the records give (village.full_names)."""
    if p.upcoming or not titles:
        return {}
    keys = [p.key] + [old for old, now in village.relooked.items() if now == p.key] \
        + [cut for cut, full in village.full_names.items() if (full, cut[1], cut[2]) == p.key]
    out: dict = {}
    for key in keys:
        for k, v in titles.get(key, {}).items():
            out.setdefault(k, v)
    return out


def plain_text(lines: list[list[Run]]) -> str:
    return "\n".join("".join(r[0] for r in line) for line in lines)


class VillagerInfoTab:
    """The tab in a TreeEditor's notebook.  The editor gives: notebook, village, edits, game,
    present (the head sheets), selected, lay (for the names), and go_to(pid)."""

    def __init__(self, editor) -> None:
        self.editor = editor
        outer = self.frame = ttk.Frame(editor.notebook)
        editor.notebook.add(outer, text=TAB_NAME)
        try:
            bg = ttk.Style(outer).lookup("TFrame", "background") or "#f0f0f0"
        except tk.TclError:
            bg = "#f0f0f0"
        text = self.text = tk.Text(outer, wrap="word", relief="flat", borderwidth=0, background=bg,
                                   padx=8, pady=8, cursor="arrow", width=34, font=("Segoe UI", 10))
        bar = ttk.Scrollbar(outer, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        # Coloured by sex but not bold (the owner, 2026-10-10: "the bold pink and blue kind of hurts my
        # eyes. you should unbold them").
        plain = ("Segoe UI", 10)
        text.tag_configure("Male", foreground=MALE, font=plain)
        text.tag_configure("Female", foreground=FEMALE, font=plain)
        text.tag_configure("unknown", foreground=UNKNOWN, font=plain)
        text.tag_configure("title", font=("Segoe UI", 14))
        text.tag_configure("heading", font=("Segoe UI", 10, "bold"), spacing1=2)
        text.tag_configure("note", foreground="#444444")
        # Partner names and the "Children (in order of birth):" line in bold (the owner, 2026-10-10),
        # their colour kept: created after the colours so its font wins.
        text.tag_configure("strong", font=("Segoe UI", 10, "bold"))
        text.tag_configure("link", underline=True)
        text.tag_bind("link", "<Enter>", lambda _e: text.configure(cursor="hand2"))
        text.tag_bind("link", "<Leave>", lambda _e: text.configure(cursor="arrow"))
        self.icon = None
        self.titles: dict = {}
        self.titles_for = None
        self.sheets: dict = {}
        self.links: dict[str, int] = {}
        self.refresh()

    def _titles(self) -> dict:
        """village_titles for the village shown, read again when it is read again (Update from
        Logs/Saves gives the editor a new Village)."""
        ed = self.editor
        if self.titles_for is not ed.village:
            folder, slot = getattr(ed, "folder", None), getattr(ed, "slot", None)
            try:
                self.titles = village_titles(folder, ed.game, slot) if folder is not None and slot is not None else {}
            except Exception:           # titles are extra: the tab still shows everything else
                self.titles = {}
            self.titles_for = ed.village
        return self.titles

    def _face(self, p: gen.Person):
        """The face the portrait shows, at ICON_ZOOM, or None (no sprite for them)."""
        ed = self.editor
        sheet = ft.sheet_name(ed.game, p)
        path = (getattr(ed, "present", None) or {}).get(sheet) if sheet else None
        row = ft.look_of(ed.edits, ed.village, p)[0]
        if path is None or row is None or row < 0:      # head 0 is a real head
            return None
        try:
            source = self.sheets.get(str(path))
            if source is None:
                source = self.sheets[str(path)] = tk.PhotoImage(master=self.text, file=str(path))
            if (row + 1) * ft.HEAD_H > source.height():
                return None
            cell = tk.PhotoImage(master=self.text)
            x0, y0 = ft.HEAD_FRAME * ft.HEAD_W, row * ft.HEAD_H
            # Only the face's visible pixels (A New Home's male faces fill only the cell's top rows).
            bx0, by0, bx1, by1 = ft.head_boxes(path).get(row, ft.DEFAULT_BOX)
            cell.tk.call(cell, "copy", source, "-from", x0 + bx0, y0 + by0, x0 + bx1, y0 + by1, "-zoom", ICON_ZOOM)
            return cell
        except tk.TclError:
            return None

    def _placeholder(self, p: gen.Person) -> tk.Canvas:
        size = 80
        c = tk.Canvas(self.text, width=size, height=size, highlightthickness=0, background=self.text.cget("background"))
        colour = {"Male": MALE, "Female": FEMALE}.get(_sex_style(p), UNKNOWN)
        if p.upcoming:
            c.create_polygon(size / 2, 6, size - 6, size / 2, size / 2, size - 6, 6, size / 2, fill="", outline=colour,
                             width=3)
        else:
            c.create_oval(8, 8, size - 8, size - 8, outline=colour, width=3)
        c.create_text(size / 2, size / 2, text="?", fill=colour, font=("Segoe UI", 18, "bold"))
        return c

    def refresh(self) -> None:
        ed, text = self.editor, self.text
        try:
            text.configure(state="normal")
        except tk.TclError:
            return
        text.delete("1.0", "end")
        for tag in self.links:
            text.tag_delete(tag)
        self.links = {}
        chosen = [q for q in getattr(ed, "selected", []) if q in ed.village.people]
        if len(chosen) != 1:
            text.insert("end", HINT, "note")
            text.configure(state="disabled")
            return
        p = ed.village.people[chosen[0]]
        lay = getattr(ed, "lay", None)
        names = getattr(lay, "names", {}) if lay is not None else {}
        self.icon = self._face(p)
        if self.icon is not None:
            text.image_create("end", image=self.icon)
        else:
            text.window_create("end", window=self._placeholder(p))
        text.insert("end", "\n")
        for n, line in enumerate(info_lines(ed.village, ed.edits, p.id, names, self._titles())):
            for words, style, pid in line:
                tags = style.split("+") + (["title"] if n == 0 else [])
                if pid is not None:
                    tag = f"go{len(self.links)}"
                    self.links[tag] = pid
                    text.tag_bind(tag, "<Button-1>", lambda _e, q=pid: self._go(q))
                    tags += ["link", tag]
                text.insert("end", words, tuple(tags))
            text.insert("end", "\n")
        text.tag_raise("title")                         # the name larger than the rest, still in its colour
        text.configure(state="disabled")

    def _go(self, pid: int) -> None:
        go_to(self.editor, pid)


def go_to(ed, pid: int) -> bool:
    """Select a villager on the tree and scroll to them: on this page, else the first page that
    shows them.  False (and a word on the status line) when no page does."""
    if pid not in ed.sc.boxes:
        for page in range(len(ft.page_spans(ed.edits, ed.village))):
            if page != ed.page:
                ed._show_page(page)
                if pid in ed.sc.boxes:
                    break
    if pid not in ed.sc.boxes:
        ed.status.set(f"{ed.village.people[pid].name} is not on the tree (taken off it).")
        return False
    ed.obj = None
    ed._select([pid])
    ed._draw_handles()
    ed._refresh_obj_panel()
    ed.update_idletasks()
    c = ed.canvas
    ed._keep_view((pid, c.winfo_width() / 2, c.winfo_height() / 2))
    return True
