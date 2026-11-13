"""The Custom Island Event Library window (v1.35.97; the owner, 2026-11-12: the branching editor lives in the patcher).

A tool of its own on the Tools tab, opened as Stew Recipes and Game Mechanics are.  It writes and keeps branching
Custom Island Events -- the node graphs of src/vv_cie_graph.py -- for one game's save folder:

    <save folder>\\Virtual Villagers Fun Patcher\\Custom Island Events\\<name>.json   the event as written
    <save folder>\\Virtual Villagers Fun Patcher\\Custom Island Events\\<name>.cieg   compiled from it at each save

The .json and the .cieg are each written through a temporary file moved over the old one.  A .cieg is only written for
an event that passes every check (vv_cie_graph.validate); an event with problems is saved as its .json alone, newer
than any old .cieg, so the game's picker never lists it until it is fixed.  Delete sends both files to the Recycle Bin
(never a hard delete) after asking.

The window is one fixed-size, resizable window: never a tall page (the patcher's page-height guard).  Left, the event
as a tree (the start, its buttons, every part, the ways on with their weights and conditions; a part reached twice is
shown once and linked after).  Right, the part chosen: its text with an Insert menu for the placeholders, its variants,
new popup or continued, its ways on, its changes (only the ones every game it is made for can do; the risky ones
marked), the roles, and the Check tab: every problem the checks find (click one to go to its part) and the chances of
every outcome, laid out as the owner's design file.  A fit meter shows, for each game, how much of the screen the
chosen part's popup takes (pages without scrolling; with the Scrolling Popups patch, only the game's text limit).

Every word on it is plain: the window shows no code names.  Like the patcher's other tool windows its words are the
patcher's own English (data/translations/patcher_strings.json holds the patcher's in-game text only).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import vv_cie_graph as cg
import vv_save_backup
import vv_tool_fonts
import vv_translations
import vv_tribe_rename
from vv_scrollbars import horizontal_bar, scrolled_listbox
from vv_tree_editor_tools import ScrollingTab

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "cie_graphs" / "the_aspiring_adventurer.json"
CAVE_EXAMPLE = ROOT / "data" / "cie_graphs" / "the_cave_explorers.json"   # questions anywhere (version 2)

TITLE = "Custom Island Event Library"
WIDTH, HEIGHT = 1180, 780
MIN_WIDTH, MIN_HEIGHT = 900, 600
RED = "#b00020"
GREEN = "#1b5e20"

INTRO = ("Write your own island events with choices and chances. Each event is kept in the save folder of the game "
         "chosen here; the game lists the ones that pass every check, and you pick one to happen from Custom Island "
         "Events in the game.")
HELP_TEXT = (
    "How an event is built\n"
    "An event starts with its first part: a popup, or a question with two buttons. Any part can be a question: "
    "choose \"A question (two buttons)\" as its kind, write both buttons' words on the Next tab and point each "
    "button at the part it leads to; ask as many questions as you like, between popups, chances and changes. After "
    "each answer the game first shows a popup of the answer's own, so a button leads to a popup (or a split that "
    "reaches one) before the next question or the end, and a question itself changes nothing. Each part can lead on to "
    "other parts; when a part has several ways on, the game picks one at random, a way with a bigger weight "
    "more often. A way can be kept for some games, some patches, or only when a role takes part; when it does "
    "not apply, its Otherwise part is used instead. A silent split shows nothing and just picks the way on.\n\n"
    "Text\n"
    "Use the Insert menu for names and words that change: (Name) is the villager's name (the full name, first "
    "and last, when the Last Names patch is on), (he/she) and the others follow the villager's sex, and "
    "(award) is the amount actually given (a fixed amount; the Island Events Scale patches can scale it). Only "
    "letters, digits, spaces and . , ! ? : - ' \" can be shown.\n\n"
    "Roles\n"
    "The main villager, and any others the event uses. If no villager fits a role the event needs, the game "
    "refuses to queue the event and says so.\n\n"
    "Deaths\n"
    "A death can be recorded as \"Died in a custom island event\", as \"Unknown causes\" (like the game's own "
    "island events), or in your own words (up to 63 characters).\n\n"
    "Fitting on the screen\n"
    "Text never runs off the screen: the fit meter shows how many pages each game needs for the chosen popup. "
    "With the Scrolling Popups patch, a popup scrolls, so only the game's text limit counts.\n\n"
    "Saving\n"
    "Save writes the event to the library of the save folder chosen at the top. Events with problems are kept "
    "but the game does not list them until the problems on the Check tab are fixed. Delete moves the event to "
    "the Recycle Bin. Export and Import share an event as a file.")

SCROLLING = "Popups scroll in my games (the Scrolling Popups patch)"
NO_FOLDER = "(no save folder found)"
NO_EVENTS = "(no events saved yet)"
NOT_SAVED = "(not saved yet)"
ENDS = "(the event ends)"
LEAVE_OUT = "(leave this way out)"
NEW_TEXT = "Write what happens here."

GAME_TITLES = {1: "Virtual Villagers - A New Home", 2: "Virtual Villagers - The Lost Children",
               3: "Virtual Villagers - The Secret City", 4: "Virtual Villagers - The Tree of Life",
               5: "Virtual Villagers - New Believers"}

# Changes, in the order the Add menu offers them, with their plain names.
EFFECT_ORDER = ("food", "tech", "pay_award", "health", "skill", "preference", "sick", "status", "vanish", "kill")
EFFECT_NAMES = {
    "food": "Add or take food",
    "tech": "Add or take tech points",
    "pay_award": "Give the award kept earlier",
    "health": "Set a villager's health",
    "skill": "Raise a villager's skill",
    "preference": "Give a villager a new like or dislike",
    "sick": "Make a villager sick",
    "status": "Make a villager a Heathen",
    "vanish": "Make a villager disappear for good",
    "kill": "A villager dies",
}
RISKY = {
    "kill": "Cannot be undone: the villager dies and gets a grave.",
    "vanish": "Cannot be undone: the villager is gone for good, with no grave.",
    "sick": "A sick villager who is not cured can die.",
    "status": "At your own risk: the villager leaves the believers and becomes a Heathen.",
}
CAUSE_WORDS = {"custom": "Died in a custom island event", "unknown": "Unknown causes"}
OWN_WORDS = "In my own words:"
TYPE_WORDS = {"popup": "A popup with text", "branch": "A silent split (no popup)",
              "question": "A question (two buttons)"}
POPUP_WORDS = {"new": "Opens a new popup", "append": "Continues the popup already open"}
JOIN_WORDS = {"space": "on the same line", "paragraph": "as a new paragraph"}
VILLAGER_SEX = {"any": "Anyone", "male": "A man", "female": "A woman"}
STRANGER_SEX = {"random": "Man or woman, at random", "male": "A man", "female": "A woman"}
KIND_WORDS = {"villager": "A villager", "stranger": "A stranger (no record, only a sex)"}


# ---- Plain words ---------------------------------------------------------------------------------------------------


def role_words(role: str) -> str:
    return "the main villager" if role == "subject" else f"the {role.replace('_', ' ')}"


def patch_words(patch: str) -> str:
    small = {"of", "the", "and", "a", "in", "on", "to", "with"}
    words = patch.split("_")
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def game_words(games) -> str:
    return " or ".join(cg.GAMES[n].name for n in games if n in cg.GAMES)


def describe_cond(c) -> str:
    """A condition in plain words: "the friend takes part", "in The Secret City", "after a_open"."""
    if c is None:
        return "always"
    (op, arg), = c.items()
    if op == "visited":
        return f"after {arg}"
    if op == "role":
        return f"{role_words(arg)} takes part"
    if op == "game":
        return "in " + game_words(arg)
    if op == "patch":
        return f"with {patch_words(arg)} on"
    if op == "not":
        (iop, iarg), = arg.items()
        if iop == "role":
            return f"{role_words(iarg)} does not take part"
        if iop == "visited":
            return f"{iarg} was not reached"
        if iop == "game":
            return "not in " + game_words(iarg)
        if iop == "patch":
            return f"with {patch_words(iarg)} off"
        return f"not ({describe_cond(arg)})"
    joiner = " and " if op == "all" else " or "
    return "(" + joiner.join(describe_cond(x) for x in arg) + ")"


def capital(words: str) -> str:
    return words[:1].upper() + words[1:]


def cond_options(g: dict, keep=None) -> list[tuple[str, object]]:
    """The conditions a way on or a variant can be given, as (plain words, condition); `keep` (one already set that
    the list does not offer, e.g. from an imported file) is listed first so it is never lost."""
    out: list[tuple[str, object]] = [("Always", None)]
    for r, role in g.get("roles", {}).items():
        if role.get("optional"):
            out.append((capital(describe_cond({"role": r})), {"role": r}))
            out.append((capital(describe_cond({"not": {"role": r}})), {"not": {"role": r}}))
    for n in g.get("games", []):
        out.append((capital(describe_cond({"game": [n]})), {"game": [n]}))
        out.append((capital(describe_cond({"not": {"game": [n]}})), {"not": {"game": [n]}}))
    for p in g.get("patches", []):
        out.append((capital(describe_cond({"patch": p})), {"patch": p}))
        out.append((capital(describe_cond({"not": {"patch": p}})), {"not": {"patch": p}}))
    for nid in g.get("nodes", {}):
        out.append((capital(describe_cond({"visited": nid})), {"visited": nid}))
        out.append((capital(describe_cond({"not": {"visited": nid}})), {"not": {"visited": nid}}))
    if keep is not None and all(c != keep for _w, c in out):
        out.insert(1, (capital(describe_cond(keep)), keep))
    return out


def describe_effect(e: dict) -> str:
    do = e.get("do")
    who = capital(role_words(e.get("role", "subject")))
    if do in ("food", "tech"):
        unit = cg.UNITS[do]
        amount = e.get("amount") if isinstance(e.get("amount"), int) else 0
        words = f"Adds {amount:,} {unit}" if amount >= 0 else f"Takes {-amount:,} {unit}"
        if e.get("scaled"):
            words += ", scaled by the Island Events Scale patches"
        if e.get("defer"):
            words += " (kept as the award: given later by \"Give the award kept earlier\")"
        return words
    if do == "pay_award":
        return "Gives the award kept earlier on the way here"
    if do == "kill":
        cause = e.get("cause", "custom")
        return f"{who} dies (recorded as \"{CAUSE_WORDS.get(cause, cause)}\")"
    if do == "vanish":
        return f"{who} disappears for good, with no grave"
    if do == "status":
        return f"{who} becomes a Heathen"
    if do == "health":
        lo, hi = e.get("min"), e.get("max")
        return f"{who}'s health becomes {lo}" if lo == hi else f"{who}'s health becomes {lo} to {hi}, at random"
    if do == "preference":
        verb = "now dislikes" if e.get("list") == "dislikes" else "now likes"
        return f"{who} {verb} {e.get('preference')}"
    if do == "skill":
        skills = ", ".join(e.get("skills") or [])
        return f"{who} gains {e.get('min')} to {e.get('max')} in one of: {skills}"
    if do == "sick":
        return f"{who} falls sick"
    return str(do)


def plain_problem(problem: str) -> str:
    """A check's words with "node X" read as "part X"."""
    return re.sub(r"\bnode (\w+)", r"part \1", problem)


def problem_node(problem: str, nodes) -> str | None:
    """The part a problem is about (the first one it names), or None."""
    for pattern in (r"\bnode (\w+)", r"popup of (\w+)", r"history (\w+)", r"a cycle: (\w+)", r"start '(\w+)'"):
        m = re.search(pattern, problem)
        if m and m.group(1) in nodes:
            return m.group(1)
    return None


# ---- The event: new, example, graph helpers ------------------------------------------------------------------------


def new_event(title: str = "A New Island Event") -> dict:
    data = {"format": cg.FORMAT, "version": cg.VERSION, "title": title, "games": sorted(cg.GAMES), "patches": [],
            "roles": {"subject": {"kind": "villager"}}, "start": "start",
            "nodes": {"start": {"text": "(Name) finds something strange on the beach."}}}
    return cg.normalize(data)[0]


def example_event(path: Path = EXAMPLE) -> dict:
    """A copy of a shipped example: The Aspiring Adventurer, or (CAVE_EXAMPLE) The Cave Explorers."""
    return cg.normalize(json.loads(path.read_text(encoding="utf-8")))[0]


def new_role() -> dict:
    """A villager role the event can do without (the format's defaults)."""
    return {"kind": "villager", "optional": True, "sex": "any", "min_age": 14, "exclude_nursing": True,
            "exclude_special": True, "believers_only": True}


def blank_node(text: str = NEW_TEXT) -> dict:
    return {"type": "popup", "popup": "new", "join": "space", "text": text, "variants": [], "effects": [],
            "children": [], "choices": [], "else": None, "summary": "", "outcome": ""}


def targets(node: dict) -> list[str]:
    out = [c["next"] for c in node.get("children", [])] + [c["else"] for c in node.get("children", []) if c["else"]]
    out += [c["next"] for c in node.get("choices", [])]
    if node.get("else"):
        out.append(node["else"])
    return out


def walkable(g: dict) -> bool:
    """Every link names a part and nothing loops back (the walk may then run)."""
    nodes = g.get("nodes") or {}
    if g.get("start") not in nodes:
        return False
    if any(t not in nodes for n in nodes.values() for t in targets(n)):
        return False
    state: dict[str, int] = {}
    for root in nodes:
        if root in state:
            continue
        stack = [(root, iter(targets(nodes[root])))]
        state[root] = 1
        while stack:
            nid, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[nid] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return False
            elif nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(targets(nodes[nxt]))))
    return True


def _weight(w) -> int:
    return w if isinstance(w, int) and not isinstance(w, bool) and w > 0 else 0


def outline(g: dict) -> list[tuple[str, str, str, str, str | None]]:
    """The tree of the event: (item, parent item, words, kind, part) -- kind "node" (a part, shown once), "link" (a
    part shown above), "choice" (a question's button; part = the question), "missing" (a link to no part), "group"."""
    nodes = g.get("nodes") or {}
    rows: list[tuple[str, str, str, str, str | None]] = []
    first: dict[str, str] = {}

    def add(parent: str, words: str, kind: str, target: str | None) -> str:
        iid = f"i{len(rows)}"
        rows.append((iid, parent, words, kind, target))
        return iid

    def label(nid: str) -> str:
        n = nodes[nid]
        if n["type"] == "branch":
            return f"{nid}  (silent split)"
        text = " ".join(n.get("text", "").split())
        if len(text) > 48:
            text = text[:47] + "..."
        return f"{nid}: {text}" if text else nid

    def visit(nid: str, parent: str, prefix: str, stack: tuple) -> None:
        if nid not in nodes:
            add(parent, f"{prefix}{nid or '(nothing)'}  (no such part: fix this link)", "missing", None)
            return
        if nid in stack:
            add(parent, f"{prefix}-> {nid}  (goes back to an earlier part: a loop)", "link", nid)
            return
        if nid in first:
            add(parent, f"{prefix}-> {nid}  (shared: shown above)", "link", nid)
            return
        iid = add(parent, prefix + label(nid), "node", nid)
        first[nid] = iid
        n = nodes[nid]
        stack = stack + (nid,)
        if n["type"] == "question":
            for i, c in enumerate(n["choices"]):
                ci = add(iid, f"Button {'AB'[i] if i < 2 else i + 1}: {c['label']}", "choice", nid)
                visit(c["next"], ci, "", stack)
            return
        total = sum(_weight(c["weight"]) for c in n["children"])
        many = len(n["children"]) > 1
        for c in n["children"]:
            words = f"{_weight(c['weight'])} in {total}: " if many else ""
            if c["if"] is not None:
                words += f"if {describe_cond(c['if'])}: "
            visit(c["next"], iid, words, stack)
            if c["else"]:
                visit(c["else"], iid, "otherwise: ", stack)
        if n["else"]:
            visit(n["else"], iid, "when no way applies: ", stack)

    start = g.get("start")
    if start in nodes:
        visit(start, "", "Start: ", ())
    else:
        add("", f"Start: {start or '(none)'}  (no such part)", "missing", None)
    orphans = [nid for nid in nodes if nid not in first]
    if orphans:
        group = add("", "Parts not reached from the start", "group", None)
        for nid in orphans:
            if nid not in first:
                visit(nid, group, "", ())
    return rows


def rename_node(g: dict, old: str, new: str) -> None:
    """Rename a part, and every link and condition that names it."""
    nodes = g["nodes"]
    g["nodes"] = {(new if k == old else k): v for k, v in nodes.items()}

    def cond(c):
        if c is None:
            return None
        (op, arg), = c.items()
        if op == "visited":
            return {"visited": new if arg == old else arg}
        if op == "not":
            return {"not": cond(arg)}
        if op in ("all", "any"):
            return {op: [cond(x) for x in arg]}
        return c

    if g.get("start") == old:
        g["start"] = new
    for n in g["nodes"].values():
        for c in n["children"]:
            c["next"] = new if c["next"] == old else c["next"]
            c["else"] = new if c["else"] == old else c["else"]
            c["if"] = cond(c["if"])
        for c in n["choices"]:
            c["next"] = new if c["next"] == old else c["next"]
        if n["else"] == old:
            n["else"] = new
        for v in n["variants"]:
            v["if"] = cond(v["if"])


def delete_node(g: dict, nid: str) -> None:
    """Take a part out: the ways on to it go too (a button that led to it is left pointing nowhere, for the
    Check tab to report)."""
    g["nodes"].pop(nid, None)
    for n in g["nodes"].values():
        n["children"] = [c for c in n["children"] if c["next"] != nid]
        for c in n["children"]:
            if c["else"] == nid:
                c["else"] = None
        if n["else"] == nid:
            n["else"] = None
        for c in n["choices"]:
            if c["next"] == nid:
                c["next"] = ""
    if g.get("start") == nid:
        g["start"] = next(iter(g["nodes"]), "")


def free_id(g: dict, stem: str = "part") -> str:
    n = 1
    while f"{stem}_{n}" in g["nodes"]:
        n += 1
    return f"{stem}_{n}"


def effect_kinds(games) -> list[str]:
    """The changes every game in `games` can make in its Custom Island Event."""
    out = []
    for kind in EFFECT_ORDER:
        cap = cg.EFFECT_CAPS[kind]
        ok = all(not cap or cg.GAMES[n].caps & cap for n in games)
        if kind == "status":
            ok = ok and all("heathen" in cg.GAMES[n].statuses for n in games)
        if ok and games:
            out.append(kind)
    return out


def common(games, attribute: str) -> list[str]:
    games = [n for n in games if n in cg.GAMES] or sorted(cg.GAMES)
    first = getattr(cg.GAMES[games[0]], attribute)
    return [w for w in first if all(w in getattr(cg.GAMES[n], attribute) for n in games)]


def new_effect(kind: str, games, role: str = "subject") -> dict:
    if kind in ("food", "tech"):
        return {"do": kind, "amount": 100, "scaled": False, "defer": False}
    if kind == "pay_award":
        return {"do": "pay_award"}
    e: dict = {"do": kind, "role": role}
    if kind == "kill":
        e["cause"] = "custom"
    elif kind == "status":
        e["status"] = "heathen"
    elif kind == "health":
        e.update(min=50, max=50)
    elif kind == "preference":
        words = common(games, "preferences")
        e.update(list="likes", preference=words[0] if words else "")
    elif kind == "skill":
        skills = common(games, "skills")
        e.update(skills=skills[:1], min=1, max=10)
    return e


# ---- The fit meter -------------------------------------------------------------------------------------------------


@dataclass
class Fit:
    used: int
    limit: int
    unit: str          # "pages" or "characters"
    over: bool
    why: str = ""

    def words(self) -> str:
        if self.why:
            return f"Runs off the screen: {self.why}"
        text = f"{self.used:,} of {self.limit:,} {self.unit}"
        return text + (" - too long" if self.over else "")


def fit_meter(g: dict, nid: str, scrolling: bool) -> dict[int, Fit | None]:
    """For each game the event is made for: how much of the screen the popup holding part `nid` takes at its
    longest (the longest names, every history); None when the part shows no popup on any history."""
    out: dict[int, Fit | None] = {}
    if not walkable(g) or nid not in g["nodes"]:
        return out
    for number in g["games"]:
        game = cg.GAMES[number]
        worst: Fit | None = None
        for ctx in cg.contexts(g, [number]):
            for path in cg.walk(g, ctx):
                for pop in path.popups:
                    if nid not in pop.nodes:
                        continue
                    if scrolling:
                        used = len(pop.worst.encode("ascii", "replace"))
                        fit = Fit(used, cg.POPUP_TEXT_MAX, "characters", used > cg.POPUP_TEXT_MAX)
                    else:
                        layout = getattr(game, pop.layout)
                        pages, why = cg.paginate(layout, g["title"], pop.worst,
                                                 cg.REFUSAL_LINES if pop.effects else 0)
                        fit = Fit(len(pages), cg.MAX_PAGES, "pages", bool(why) or len(pages) > cg.MAX_PAGES,
                                  why or "")
                    if worst is None or (fit.over, fit.used) > (worst.over, worst.used):
                        worst = fit
        out[number] = worst
    return out


def chances_text(g: dict, game: int, patches=(), roles=None) -> str:
    if not walkable(g):
        return "The chances are shown once every link leads to a part and no part leads back to an earlier one."
    if game not in g["games"]:
        return "This event is not made for that game."
    try:
        return cg.chances_table(g, game, patches, roles)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return f"The chances cannot be worked out yet ({exc}). Fix the problems above first."


# ---- The library ---------------------------------------------------------------------------------------------------


def write_atomic(path: Path, payload: bytes) -> None:
    """`payload` into `path` through a temporary file in the same folder, moved over the old file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tmp-", suffix=path.suffix, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def event_json(g: dict) -> bytes:
    return (json.dumps(g, indent=2) + "\n").encode("utf-8")


@dataclass
class Saved:
    json: Path
    cieg: Path | None
    problems: list[str] = field(default_factory=list)


def save_event(g: dict, save_folder: Path, stem: str, scrolling: bool = False) -> Saved:
    """The event into the library: its .json, and its .cieg when it passes every check."""
    checked, problems = cg.validate(g, scrolling)
    if not problems:
        json_path, cieg_path = cg.save_to_library(checked, save_folder, stem)
        return Saved(json_path, cieg_path, [])
    path = cg.library_folder(save_folder) / (stem + cg.GRAPH_SUFFIX)
    write_atomic(path, event_json(g))
    return Saved(path, None, problems)


def library_events(save_folder: Path | None, scrolling: bool = False) -> list[tuple[str, int]]:
    """(name, problems) for every event in the library."""
    if save_folder is None:
        return []
    return [(stem, len(problems)) for stem, (_g, problems) in cg.read_library(save_folder, scrolling).items()]


def read_event(path: Path) -> dict:
    """An event file, every default filled in; ValueError when it is not an event at all."""
    g, problems = cg.normalize(json.loads(Path(path).read_text(encoding="utf-8")))
    if not g.get("nodes"):
        raise ValueError("; ".join(problems) or "it has no parts")
    return g


# The dialogs, replaced in the tests.
ASK_YES_NO = messagebox.askyesno
SHOW_INFO = messagebox.showinfo
SHOW_ERROR = messagebox.showerror
ASK_STRING = simpledialog.askstring
ASK_OPEN = filedialog.askopenfilename
ASK_SAVE = filedialog.asksaveasfilename
RECYCLE_SHELL = None


# ---- The window ----------------------------------------------------------------------------------------------------


def open_cie_library(app, build=None) -> tk.Toplevel:
    """The window, opened at `build`'s game (or the first game)."""
    window = tk.Toplevel(app)
    window.title(TITLE)
    window.transient(app)
    width = min(WIDTH, max(MIN_WIDTH, window.winfo_screenwidth() - 80))
    height = min(HEIGHT, max(MIN_HEIGHT, window.winfo_screenheight() - 120))
    window.geometry(f"{width}x{height}")
    window.minsize(MIN_WIDTH, MIN_HEIGHT)
    window.resizable(True, True)
    window.cie = Library(window, app, build)
    return window


class Library:
    def __init__(self, window: tk.Toplevel, app, build) -> None:
        self.window = window
        self.app = app
        self.g = new_event()
        self.stem: str | None = None
        self.dirty = False
        self.nid = self.g["start"]
        self.child_index: int | None = None
        self.effect_index: int | None = None
        self.role_id: str | None = "subject"
        self.problems: list[str] = []
        self.folders: list[Path] = []
        self._loading = False
        self._job = None
        self._closed = False
        self.documents = vv_save_backup.documents_folder()
        builds = getattr(app, "builds", None) or []
        self.titles = [b.title for b in builds] or list(GAME_TITLES.values())
        self.game_numbers = [vv_tribe_rename.game_for_title(t).number for t in self.titles]
        self.fonts = vv_tool_fonts.fonts(window)
        style = ttk.Style(window)
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        style.configure("CIE.Treeview", rowheight=line + vv_tool_fonts.LINE_GAP)

        outer = ttk.Frame(window, padding=10)
        outer.pack(fill="both", expand=True)
        self._build_top(outer)
        self._build_bottom(outer)
        panes = ttk.PanedWindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self._build_tree(left)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self._tab_event()
        self._tab_text()
        self._tab_next()
        self._tab_effects()
        self._tab_roles()
        self._tab_check()
        window.protocol("WM_DELETE_WINDOW", self.close)

        first = vv_tribe_rename.game_for_title(build.title).number if build is not None else self.game_numbers[0]
        self.game_box.current(self.game_numbers.index(first) if first in self.game_numbers else 0)
        self.find_folders()
        self.load_event(new_event(), None)

    # ---- layout ----

    def _build_top(self, outer) -> None:
        top = ttk.Frame(outer)
        top.pack(fill="x")
        intro = ttk.Label(top, text=INTRO, justify="left", wraplength=MIN_WIDTH - 60)
        intro.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        top.bind("<Configure>", lambda e: intro.configure(wraplength=max(300, e.width - 8)), add="+")
        ttk.Label(top, text="Game:").grid(row=1, column=0, sticky="w")
        self.game_box = ttk.Combobox(top, state="readonly", width=22,
                                     values=[cg.GAMES[n].name for n in self.game_numbers])
        self.game_box.grid(row=1, column=1, sticky="w", padx=(4, 12))
        self.game_box.bind("<<ComboboxSelected>>", lambda _e: self.find_folders())
        ttk.Label(top, text="Save folder:").grid(row=1, column=2, sticky="w")
        self.folder_box = ttk.Combobox(top, state="readonly", width=34)
        self.folder_box.grid(row=1, column=3, sticky="we", padx=(4, 12))
        self.folder_box.bind("<<ComboboxSelected>>", lambda _e: self.list_library())
        ttk.Label(top, text="Event in the library:").grid(row=1, column=4, sticky="w")
        self.event_box = ttk.Combobox(top, state="readonly", width=34)
        self.event_box.grid(row=1, column=5, sticky="we", padx=(4, 0))
        top.columnconfigure(3, weight=1)
        top.columnconfigure(5, weight=1)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(6, 0))
        self.buttons = {}
        for words, command in (("New", self.new), ("Open", self.open_selected), ("Save", self.save),
                               ("Save As...", self.save_as), ("Duplicate", self.duplicate),
                               ("Delete...", self.delete), ("Import...", self.import_event),
                               ("Export...", self.export_event),
                               ("New from The Aspiring Adventurer", self.new_from_example),
                               ("New from The Cave Explorers", self.new_from_cave)):
            button = ttk.Button(buttons, text=words, command=command)
            button.pack(side="left", padx=(0, 4))
            self.buttons[words] = button
        self.scrolling = tk.BooleanVar(master=self.window, value=False)
        ttk.Checkbutton(buttons, text=SCROLLING, variable=self.scrolling,
                        command=self.schedule_refresh).pack(side="right")

    def _build_bottom(self, outer) -> None:
        bottom = ttk.Frame(outer)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        self.status = ttk.Label(bottom, text="", justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right")
        ttk.Button(bottom, text="Help", command=lambda: SHOW_INFO(TITLE, HELP_TEXT, parent=self.window)).pack(
            side="right", padx=(0, 6))

    def _build_tree(self, left) -> None:
        ttk.Label(left, text="The event", font=self.fonts["label"]).pack(anchor="w")
        tools = ttk.Frame(left)
        tools.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(tools, text="Add a part after this one", command=self.add_part).pack(side="left")
        ttk.Button(tools, text="Delete this part...", command=self.delete_part).pack(side="left", padx=(6, 0))
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True, pady=(4, 0))
        self.tree = ttk.Treeview(holder, show="tree", selectmode="browse", style="CIE.Treeview")
        bar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        horizontal_bar(self.tree)
        self.tree.column("#0", width=380, stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self._tree_selected)
        self.tree_rows: dict[str, tuple[str, str | None]] = {}
        self.first_item: dict[str, str] = {}

    def _tab_event(self) -> None:
        page = ScrollingTab(self.tabs, "Event")
        self.event_page = page
        ttk.Label(page, text="Title (shown at the top of every popup):").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(master=self.window)
        ttk.Entry(page, textvariable=self.title_var, width=50).grid(row=1, column=0, columnspan=3, sticky="we")
        self.title_var.trace_add("write", lambda *_: self._set("title", self.title_var.get()))
        ttk.Label(page, text="Made for these games:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.game_vars: dict[int, tk.BooleanVar] = {}
        games = ttk.Frame(page)
        games.grid(row=3, column=0, columnspan=3, sticky="w")
        for n, game in cg.GAMES.items():
            var = tk.BooleanVar(master=self.window)
            ttk.Checkbutton(games, text=game.name, variable=var, command=self._games_changed).grid(
                row=(n - 1) // 3, column=(n - 1) % 3, sticky="w", padx=(0, 12))
            self.game_vars[n] = var
        ttk.Label(page, text="Patches the event can check (their short names, separated by commas: a-z, 0-9 and _):"
                  ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.patches_var = tk.StringVar(master=self.window)
        ttk.Entry(page, textvariable=self.patches_var, width=50).grid(row=5, column=0, columnspan=3, sticky="we")
        self.patches_var.trace_add("write", lambda *_: self._patches_changed())
        ttk.Label(page, text="The first part:").grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.start_box = ttk.Combobox(page, state="readonly", width=30)
        self.start_box.grid(row=7, column=0, sticky="w")
        self.start_box.bind("<<ComboboxSelected>>", lambda _e: self._set("start", self.start_box.get()))
        note = ttk.Label(page, justify="left", wraplength=500, text=(
            "The game needs no particular villagers for a Custom Island Event: you choose when it happens. If no "
            "villager fits a role the event needs (Roles tab), the game refuses to queue it and says so."))
        note.grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 0))
        page.columnconfigure(0, weight=1)

    def _tab_text(self) -> None:
        page = ScrollingTab(self.tabs, "Text")
        self.text_page = page
        row = ttk.Frame(page)
        row.pack(fill="x")
        ttk.Label(row, text="Name of this part:").pack(side="left")
        self.name_var = tk.StringVar(master=self.window)
        ttk.Entry(row, textvariable=self.name_var, width=20).pack(side="left", padx=(4, 4))
        ttk.Button(row, text="Rename", command=self.rename_part).pack(side="left")
        ttk.Label(row, text="Kind:").pack(side="left", padx=(12, 4))
        self.type_box = ttk.Combobox(row, state="readonly", width=26, values=list(TYPE_WORDS.values()))
        self.type_box.pack(side="left")
        self.type_box.bind("<<ComboboxSelected>>", lambda _e: self._type_changed())

        shape = ttk.Frame(page)
        shape.pack(fill="x", pady=(8, 0))
        self.popup_box = ttk.Combobox(shape, state="readonly", width=32, values=list(POPUP_WORDS.values()))
        self.popup_box.pack(side="left")
        self.popup_box.bind("<<ComboboxSelected>>", lambda _e: self._node_set(
            "popup", next(k for k, v in POPUP_WORDS.items() if v == self.popup_box.get())))
        ttk.Label(shape, text="joined").pack(side="left", padx=(8, 4))
        self.join_box = ttk.Combobox(shape, state="readonly", width=20, values=list(JOIN_WORDS.values()))
        self.join_box.pack(side="left")
        self.join_box.bind("<<ComboboxSelected>>", lambda _e: self._node_set(
            "join", next(k for k, v in JOIN_WORDS.items() if v == self.join_box.get())))

        which = ttk.Frame(page)
        which.pack(fill="x", pady=(8, 0))
        ttk.Label(which, text="Text shown:").pack(side="left")
        self.variant_box = ttk.Combobox(which, state="readonly", width=30)
        self.variant_box.pack(side="left", padx=(4, 4))
        self.variant_box.bind("<<ComboboxSelected>>", lambda _e: self._show_text())
        ttk.Button(which, text="Add a variant", command=self.add_variant).pack(side="left")
        ttk.Button(which, text="Remove variant", command=self.remove_variant).pack(side="left", padx=(4, 0))
        self.insert_button = ttk.Menubutton(which, text="Insert")
        self.insert_button.pack(side="right")
        self.insert_menu = tk.Menu(self.insert_button, tearoff=False)
        self.insert_button["menu"] = self.insert_menu
        cond_row = ttk.Frame(page)
        cond_row.pack(fill="x", pady=(4, 0))
        ttk.Label(cond_row, text="This variant is shown:").pack(side="left")
        self.variant_cond = ttk.Combobox(cond_row, state="readonly", width=44)
        self.variant_cond.pack(side="left", padx=(4, 0))
        self.variant_cond.bind("<<ComboboxSelected>>", lambda _e: self._variant_cond_changed())
        self.variant_cond_row = cond_row

        holder = ttk.Frame(page)
        holder.pack(fill="x", pady=(6, 0))
        box = vv_tool_fonts.tool_text(holder, wrap="word", height=9, width=60, padx=6, pady=6, borderwidth=1,
                                      relief="solid", undo=True)
        bar = ttk.Scrollbar(holder, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=bar.set, spacing3=vv_tool_fonts.LINE_GAP)
        bar.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        box.bind("<<Modified>>", self._text_modified)
        self.text_box = box
        self.chars_label = ttk.Label(page, text="")
        self.chars_label.pack(anchor="w", pady=(2, 0))

        ttk.Label(page, text="Fits on the screen (the popup this part is in, with the longest names):",
                  font=self.fonts["label"]).pack(anchor="w", pady=(10, 2))
        self.fit_frame = ttk.Frame(page)
        self.fit_frame.pack(fill="x")
        self.fit_rows: dict[int, tuple[ttk.Progressbar, ttk.Label]] = {}

    def _tab_next(self) -> None:
        page = ScrollingTab(self.tabs, "Next")
        self.next_page = page
        self.next_intro = ttk.Label(page, justify="left", wraplength=500, text=(
            "The ways on from this part. The game picks one at random: a bigger weight is picked more often. A way "
            "kept for some games, patches or roles is replaced by its Otherwise part when it does not apply."))
        self.next_intro.pack(anchor="w")
        ways = ttk.Frame(page)
        ways.pack(fill="x")
        self.ways_frame = ways
        holder = ttk.Frame(ways)
        holder.pack(fill="x", pady=(6, 0))
        columns = ("next", "weight", "chance", "if", "else")
        self.children_table = ttk.Treeview(holder, columns=columns, show="headings", height=6,
                                           selectmode="browse", style="CIE.Treeview")
        for col, words, width in (("next", "Goes to", 120), ("weight", "Weight", 60), ("chance", "Chance", 70),
                                  ("if", "Only if", 190), ("else", "Otherwise", 110)):
            self.children_table.heading(col, text=words)
            self.children_table.column(col, width=width, stretch=col in ("if",))
        bar = ttk.Scrollbar(holder, orient="vertical", command=self.children_table.yview)
        self.children_table.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.children_table.pack(side="left", fill="x", expand=True)
        horizontal_bar(self.children_table)
        self.children_table.bind("<<TreeviewSelect>>", self._child_selected)

        form = ttk.Frame(ways)
        form.pack(fill="x", pady=(6, 0))
        ttk.Label(form, text="Goes to:").grid(row=0, column=0, sticky="w")
        self.next_var = tk.StringVar(master=self.window)
        self.next_box = ttk.Combobox(form, textvariable=self.next_var, width=24)
        self.next_box.grid(row=0, column=1, sticky="w", padx=(4, 12))
        self.next_var.trace_add("write", lambda *_: self._child_set("next", self.next_var.get().strip()))
        ttk.Label(form, text="Weight:").grid(row=0, column=2, sticky="w")
        self.weight_var = tk.StringVar(master=self.window)
        ttk.Spinbox(form, from_=1, to=cg.MAX_WEIGHT, textvariable=self.weight_var, width=7).grid(
            row=0, column=3, sticky="w", padx=(4, 0))
        self.weight_var.trace_add("write", lambda *_: self._weight_changed())
        ttk.Label(form, text="Only if:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.if_box = ttk.Combobox(form, state="readonly", width=44)
        self.if_box.grid(row=1, column=1, columnspan=3, sticky="w", padx=(4, 0), pady=(4, 0))
        self.if_box.bind("<<ComboboxSelected>>", lambda _e: self._child_cond_changed())
        ttk.Label(form, text="Otherwise:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.else_box = ttk.Combobox(form, state="readonly", width=24)
        self.else_box.grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        self.else_box.bind("<<ComboboxSelected>>", lambda _e: self._child_set(
            "else", None if self.else_box.get() == LEAVE_OUT else self.else_box.get()))
        actions = ttk.Frame(ways)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Add a way on", command=self.add_child).pack(side="left")
        ttk.Button(actions, text="Remove this way", command=self.remove_child).pack(side="left", padx=(6, 0))

        self.choice_frame = ttk.Frame(page)
        self.choice_vars: list[tuple[tk.StringVar, ttk.Combobox]] = []
        for i in range(2):
            ttk.Label(self.choice_frame, text=f"Button {'AB'[i]}:").grid(row=i, column=0, sticky="w", pady=2)
            label = tk.StringVar(master=self.window)
            ttk.Entry(self.choice_frame, textvariable=label, width=30).grid(row=i, column=1, sticky="w", padx=4)
            ttk.Label(self.choice_frame, text="goes to").grid(row=i, column=2, sticky="w")
            box = ttk.Combobox(self.choice_frame, state="readonly", width=20)
            box.grid(row=i, column=3, sticky="w", padx=4)
            label.trace_add("write", lambda *_a, i=i: self._choice_set(i, "label"))
            box.bind("<<ComboboxSelected>>", lambda _e, i=i: self._choice_set(i, "next"))
            self.choice_vars.append((label, box))

        other = ttk.Frame(page)
        other.pack(fill="x", pady=(12, 0))
        self.other_frame = other
        ttk.Label(other, text="When no way applies, go to:").grid(row=0, column=0, sticky="w")
        self.node_else_box = ttk.Combobox(other, state="readonly", width=24)
        self.node_else_box.grid(row=0, column=1, sticky="w", padx=(4, 0))
        self.node_else_box.bind("<<ComboboxSelected>>", lambda _e: self._node_set(
            "else", None if self.node_else_box.get() == ENDS else self.node_else_box.get()))
        ttk.Label(other, text="Words for this ending in the chances table:").grid(row=1, column=0, sticky="w",
                                                                                 pady=(6, 0))
        self.summary_var = tk.StringVar(master=self.window)
        ttk.Entry(other, textvariable=self.summary_var, width=40).grid(row=1, column=1, sticky="w", padx=(4, 0),
                                                                       pady=(6, 0))
        self.summary_var.trace_add("write", lambda *_: self._node_set("summary", self.summary_var.get()))
        ttk.Label(other, text="Its group under \"In all\" (empty: from its changes):").grid(row=2, column=0,
                                                                                            sticky="w", pady=(4, 0))
        self.outcome_var = tk.StringVar(master=self.window)
        ttk.Entry(other, textvariable=self.outcome_var, width=40).grid(row=2, column=1, sticky="w", padx=(4, 0),
                                                                       pady=(4, 0))
        self.outcome_var.trace_add("write", lambda *_: self._node_set("outcome", self.outcome_var.get()))

    def _tab_effects(self) -> None:
        page = ScrollingTab(self.tabs, "Changes")
        self.effects_page = page
        ttk.Label(page, justify="left", wraplength=500, text=(
            "What happens to the village when this part is reached, in order. Only the changes every game this "
            "event is made for can do are offered.")).pack(anchor="w")
        holder, self.effect_list = scrolled_listbox(page, height=6, width=70, exportselection=False)
        holder.pack(fill="x", pady=(6, 0))
        self.effect_list.bind("<<ListboxSelect>>", self._effect_selected)
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(6, 0))
        self.add_effect_button = ttk.Menubutton(actions, text="Add a change")
        self.add_effect_button.pack(side="left")
        self.add_effect_menu = tk.Menu(self.add_effect_button, tearoff=False)
        self.add_effect_button["menu"] = self.add_effect_menu
        ttk.Button(actions, text="Remove", command=self.remove_effect).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Move up", command=lambda: self.move_effect(-1)).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Move down", command=lambda: self.move_effect(1)).pack(side="left", padx=(6, 0))
        self.effect_warning = ttk.Label(page, text="", foreground=RED, font=self.fonts["label"], wraplength=500)
        self.effect_warning.pack(anchor="w", pady=(6, 0))
        self.effect_form = ttk.Frame(page)
        self.effect_form.pack(fill="x", pady=(4, 0))

    def _tab_roles(self) -> None:
        page = ScrollingTab(self.tabs, "Roles")
        self.roles_page = page
        ttk.Label(page, justify="left", wraplength=500, text=(
            "Who takes part. The main villager is always needed. If no villager fits a role the event needs, the "
            "game refuses to queue the event and says so. (Name) shows a villager's full name when the Last Names "
            "patch is on; a stranger has no name.")).pack(anchor="w")
        holder = ttk.Frame(page)
        holder.pack(fill="x", pady=(6, 0))
        columns = ("role", "kind", "needed", "sex", "age")
        self.roles_table = ttk.Treeview(holder, columns=columns, show="headings", height=5, selectmode="browse",
                                        style="CIE.Treeview")
        for col, words, width in (("role", "Role", 120), ("kind", "Who", 110), ("needed", "Needed", 70),
                                  ("sex", "Man or woman", 140), ("age", "Youngest age", 90)):
            self.roles_table.heading(col, text=words)
            self.roles_table.column(col, width=width)
        bar = ttk.Scrollbar(holder, orient="vertical", command=self.roles_table.yview)
        self.roles_table.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.roles_table.pack(side="left", fill="x", expand=True)
        horizontal_bar(self.roles_table)
        self.roles_table.bind("<<TreeviewSelect>>", self._role_selected)
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Add a role...", command=self.add_role).pack(side="left")
        ttk.Button(actions, text="Remove this role", command=self.remove_role).pack(side="left", padx=(6, 0))
        self.role_form = ttk.Frame(page)
        self.role_form.pack(fill="x", pady=(8, 0))

    def _tab_check(self) -> None:
        page = ScrollingTab(self.tabs, "Check")
        self.check_page = page
        self.check_status = ttk.Label(page, text="", font=self.fonts["label"])
        self.check_status.pack(anchor="w")
        ttk.Label(page, text="Click a problem to go to its part.").pack(anchor="w")
        holder = ttk.Frame(page)
        holder.pack(fill="x", pady=(4, 0))
        problems = vv_tool_fonts.tool_text(holder, wrap="word", height=8, width=60, padx=6, pady=6, borderwidth=1,
                                           relief="solid", cursor="hand2")
        bar = ttk.Scrollbar(holder, orient="vertical", command=problems.yview)
        problems.configure(yscrollcommand=bar.set, spacing3=vv_tool_fonts.LINE_GAP, state="disabled")
        bar.pack(side="right", fill="y")
        problems.pack(side="left", fill="both", expand=True)
        self.problem_box = problems

        ttk.Label(page, text="The chances of every outcome", font=self.fonts["heading"]).pack(anchor="w",
                                                                                           pady=(12, 2))
        picks = ttk.Frame(page)
        picks.pack(fill="x")
        ttk.Label(picks, text="In:").pack(side="left")
        self.chance_game = ttk.Combobox(picks, state="readonly", width=20)
        self.chance_game.pack(side="left", padx=(4, 8))
        self.chance_game.bind("<<ComboboxSelected>>", lambda _e: self.show_chances())
        self.chance_picks = ttk.Frame(picks)
        self.chance_picks.pack(side="left")
        self.chance_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        holder = ttk.Frame(page)
        holder.pack(fill="x", pady=(4, 0))
        table = vv_tool_fonts.tool_text(holder, wrap="none", height=18, width=60, padx=6, pady=6, borderwidth=1,
                                        relief="solid")
        bar = ttk.Scrollbar(holder, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=bar.set, spacing3=vv_tool_fonts.LINE_GAP, state="disabled",
                        font=("Consolas", 10))
        bar.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)
        horizontal_bar(table)
        self.chances_box = table

    # ---- loading and showing ----

    def load_event(self, g: dict, stem: str | None, dirty: bool = False) -> None:
        self.g = g
        self.stem = stem
        self.dirty = dirty
        self.nid = g["start"] if g["start"] in g["nodes"] else next(iter(g["nodes"]), "")
        self.child_index = None
        self.effect_index = None
        self.role_id = "subject" if "subject" in g["roles"] else next(iter(g["roles"]), None)
        self.tree_rows.clear()              # a new event's tree opens fully
        self._loading = True
        try:
            self.title_var.set(g["title"])
            for n, var in self.game_vars.items():
                var.set(n in g["games"])
            self.patches_var.set(", ".join(g["patches"]))
        finally:
            self._loading = False
        self.refresh_now()
        self.show_node()
        self.show_roles()

    def node(self) -> dict | None:
        return self.g["nodes"].get(self.nid)

    def changed(self) -> None:
        self.dirty = True
        self.schedule_refresh()

    def schedule_refresh(self) -> None:
        if self._closed:
            return
        if self._job is not None:
            self.window.after_cancel(self._job)
        self._job = self.window.after(300, self.refresh_now)

    def refresh_now(self) -> None:
        """Every check again: the tree, the problems, the chances, the fit meter and the status line."""
        if self._job is not None:
            try:
                self.window.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self._closed:
            return
        _checked, self.problems = cg.validate(self.g, self.scrolling.get())
        self.show_tree()
        self.show_problems()
        self.show_chances()
        self.show_fit()
        self.show_children_table()
        self.show_status()
        names = list(self.g["nodes"])
        self.start_box.configure(values=names)
        self.start_box.set(self.g["start"])

    def show_status(self) -> None:
        name = self.stem or NOT_SAVED
        saved = "" if not self.dirty else " - changed, not saved"
        if self.problems:
            words = (f"{name}{saved}. {len(self.problems)} problem(s) to fix on the Check tab: the game will not "
                     "list this event until they are fixed.")
            self.status.configure(text=words, foreground=RED)
        else:
            self.status.configure(text=f"{name}{saved}. No problems: the game can play this event.",
                                  foreground=GREEN)
        self.window.title(TITLE + (" - " + (self.stem or NOT_SAVED)) + (" *" if self.dirty else ""))

    def show_tree(self) -> None:
        self._loading = True
        try:
            open_items = {self.tree_rows[i][1] for i in self.tree_rows
                          if self.tree.exists(i) and self.tree.item(i, "open")} if self.tree_rows else None
            self.tree.delete(*self.tree.get_children())
            self.tree_rows.clear()
            self.first_item.clear()
            for iid, parent, words, kind, target in outline(self.g):
                self.tree.insert(parent, "end", iid=iid, text=words,
                                 open=open_items is None or target in open_items or kind in ("group", "choice"))
                self.tree_rows[iid] = (kind, target)
                if kind == "node":
                    self.first_item[target] = iid
            item = self.first_item.get(self.nid)
            if item:
                self.tree.selection_set(item)
                self.tree.see(item)
        finally:
            self._loading = False

    def _tree_selected(self, _event=None) -> None:
        if self._loading:
            return
        picked = self.tree.selection()
        if not picked:
            return
        kind, target = self.tree_rows.get(picked[0], ("", None))
        if target is None or target not in self.g["nodes"]:
            return
        if kind == "link" and self.first_item.get(target) and self.first_item[target] != picked[0]:
            self.select_node(target)
            return
        if target != self.nid:
            self.nid = target
            self.child_index = None
            self.effect_index = None
            self.show_node()
            self.show_fit()

    def select_node(self, nid: str, tab: str | None = None) -> None:
        if nid not in self.g["nodes"]:
            return
        self.nid = nid
        self.child_index = None
        self.effect_index = None
        item = self.first_item.get(nid)
        if item:
            self._loading = True
            try:
                self.tree.selection_set(item)
                self.tree.see(item)
            finally:
                self._loading = False
        self.show_node()
        self.show_fit()
        if tab:
            for t in self.tabs.tabs():
                if self.tabs.tab(t, "text") == tab:
                    self.tabs.select(t)

    def show_node(self) -> None:
        n = self.node()
        self._loading = True
        try:
            self.name_var.set(self.nid if n else "")
            if n is None:
                return
            self.type_box.set(TYPE_WORDS[n["type"]])
            self.popup_box.set(POPUP_WORDS[n["popup"]])
            self.join_box.set(JOIN_WORDS[n["join"]])
            state = "readonly" if n["type"] == "popup" else "disabled"
            self.popup_box.configure(state=state)
            self.join_box.configure(state=state)
            variants = ["The usual text"] + [f"Variant {i + 1}: {capital(describe_cond(v['if']))}"
                                             for i, v in enumerate(n["variants"])]
            self.variant_box.configure(values=variants)
            self.variant_box.current(0)
            self._build_insert_menu()
        finally:
            self._loading = False
        self._show_text()
        self.show_children_table()
        self.show_effects()

    def _variant(self) -> int | None:
        index = self.variant_box.current()
        return index - 1 if index > 0 else None

    def _show_text(self) -> None:
        n = self.node()
        if n is None:
            return
        v = self._variant()
        text = n["variants"][v]["text"] if v is not None and v < len(n["variants"]) else n["text"]
        self._loading = True
        try:
            self.text_box.configure(state="normal")
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", text)
            self.text_box.edit_modified(False)
            self.text_box.edit_reset()
            if n["type"] == "branch":
                self.text_box.configure(state="disabled")
            if v is not None:
                options = cond_options(self.g, n["variants"][v]["if"])
                self.variant_cond.configure(values=[w for w, _c in options])
                self.variant_cond.set(next(w for w, c in options if c == n["variants"][v]["if"]))
                self.variant_cond.configure(state="readonly")
            else:
                self.variant_cond.set("")
                self.variant_cond.configure(state="disabled")
        finally:
            self._loading = False
        self._count_chars(text)

    def _count_chars(self, text: str) -> None:
        used = len(text.encode("ascii", "replace"))
        words = f"{used:,} of {cg.NODE_TEXT_MAX:,} characters"
        self.chars_label.configure(text=words, foreground=RED if used > cg.NODE_TEXT_MAX else "")

    def _text_modified(self, _event=None) -> None:
        if not self.text_box.edit_modified():
            return
        self.text_box.edit_modified(False)
        if self._loading:
            return
        n = self.node()
        if n is None or n["type"] == "branch":
            return
        text = self.text_box.get("1.0", "end-1c")
        v = self._variant()
        if v is not None:
            n["variants"][v]["text"] = text
        else:
            n["text"] = text
        self._count_chars(text)
        self.changed()

    def _build_insert_menu(self) -> None:
        menu = self.insert_menu
        menu.delete(0, "end")
        for r, role in self.g["roles"].items():
            sub = tk.Menu(menu, tearoff=False)
            prefix = "" if r == "subject" else f"{r}."
            if role["kind"] == "villager":
                sub.add_command(label="Name", command=lambda t=f"({prefix}Name)": self.insert(t))
            for key in cg.PRONOUNS:
                big = "/".join(w.capitalize() for w in key.split("/"))
                sub.add_command(label=f"{big.replace('/', ' or ')} (starting a sentence)",
                                command=lambda t=f"({prefix}{big})": self.insert(t))
                sub.add_command(label=key.replace("/", " or "), command=lambda t=f"({prefix}{key})": self.insert(t))
            menu.add_cascade(label=capital(role_words(r)), menu=sub)
        menu.add_separator()
        menu.add_command(label="The award's amount", command=lambda: self.insert("(award)"))
        menu.add_command(label="The award's kind (food or tech points)", command=lambda: self.insert("(award_unit)"))

    def insert(self, token: str) -> None:
        if str(self.text_box.cget("state")) == "disabled":
            return
        self.text_box.insert("insert", token)
        self.text_box.focus_set()

    def show_fit(self) -> None:
        for child in self.fit_frame.winfo_children():
            child.destroy()
        self.fit_rows.clear()
        n = self.node()
        if n is None:
            return
        if n["type"] == "branch":
            ttk.Label(self.fit_frame, text="A silent split shows no popup.").grid(row=0, column=0, sticky="w")
            return
        meter = fit_meter(self.g, self.nid, self.scrolling.get())
        if not meter:
            ttk.Label(self.fit_frame, text="Shown once every link leads to a part and nothing loops back.").grid(
                row=0, column=0, sticky="w")
            return
        for row, (number, fit) in enumerate(meter.items()):
            ttk.Label(self.fit_frame, text=cg.GAMES[number].name, width=18).grid(row=row, column=0, sticky="w",
                                                                                 pady=1)
            if fit is None:
                ttk.Label(self.fit_frame, text="Not shown in this game.").grid(row=row, column=1, columnspan=2,
                                                                              sticky="w")
                continue
            bar = ttk.Progressbar(self.fit_frame, length=180, maximum=fit.limit,
                                  value=min(fit.used, fit.limit))
            bar.grid(row=row, column=1, sticky="w", padx=(4, 8))
            label = ttk.Label(self.fit_frame, text=fit.words(), foreground=RED if fit.over else "")
            label.grid(row=row, column=2, sticky="w")
            self.fit_rows[number] = (bar, label)

    def _set(self, key: str, value) -> None:
        if self._loading:
            return
        self.g[key] = value
        self.changed()

    def _games_changed(self) -> None:
        if self._loading:
            return
        self.g["games"] = sorted(n for n, var in self.game_vars.items() if var.get())
        self.show_effects()
        self.changed()

    def _patches_changed(self) -> None:
        if self._loading:
            return
        self.g["patches"] = [p.strip() for p in self.patches_var.get().split(",") if p.strip()]
        self.changed()

    def _node_set(self, key: str, value) -> None:
        n = self.node()
        if self._loading or n is None:
            return
        n[key] = value
        self.changed()

    def _type_changed(self) -> None:
        n = self.node()
        if n is None:
            return
        kind = next(k for k, v in TYPE_WORDS.items() if v == self.type_box.get())
        if kind == n["type"]:
            return
        if kind == "branch" and (n["text"].strip() or n["variants"]):
            if not ASK_YES_NO(TITLE, "A silent split shows no popup, so this part's text and variants will be "
                                     "taken out. Go on?", parent=self.window):
                self.type_box.set(TYPE_WORDS[n["type"]])
                return
            n["text"], n["variants"] = "", []
        if kind == "question":
            if self.nid != self.g["start"]:
                self.g["version"] = max(self.g.get("version", 1), 2)   # questions anywhere: version 2
            n["choices"] = (n["choices"] + [{"label": "Yes", "next": c["next"]} for c in n["children"]]
                            + [{"label": "No", "next": ""}, {"label": "No", "next": ""}])[:2]
            n["children"], n["else"], n["popup"] = [], None, "new"
        elif n["type"] == "question":
            n["children"] = [{"next": c["next"], "weight": 1, "if": None, "else": None}
                             for c in n["choices"] if c["next"]]
            n["choices"] = []
        if kind != "branch" and not n["text"].strip():
            n["text"] = NEW_TEXT
        if kind != "popup":
            n["popup"] = "new"
        n["type"] = kind
        self.changed()
        self.show_node()

    def add_variant(self) -> None:
        n = self.node()
        if n is None or n["type"] == "branch":
            return
        options = cond_options(self.g)
        n["variants"].append({"if": options[1][1] if len(options) > 1 else {"game": [self.g["games"][0]]},
                              "text": n["text"]})
        self.changed()
        self.show_node()
        self.variant_box.current(len(n["variants"]))
        self._show_text()

    def remove_variant(self) -> None:
        n, v = self.node(), self._variant()
        if n is None or v is None:
            return
        del n["variants"][v]
        self.changed()
        self.show_node()

    def _variant_cond_changed(self) -> None:
        n, v = self.node(), self._variant()
        if n is None or v is None:
            return
        options = dict(cond_options(self.g, n["variants"][v]["if"]))
        n["variants"][v]["if"] = options.get(self.variant_cond.get())
        index = self.variant_box.current()
        self.changed()
        self.show_node()
        self.variant_box.current(index)
        self._show_text()

    # ---- the ways on ----

    def show_children_table(self) -> None:
        n = self.node()
        table = self.children_table
        table.delete(*table.get_children())
        if n is None:
            return
        question = n["type"] == "question"
        names = list(self.g["nodes"])
        if question:
            self.ways_frame.pack_forget()
            self.other_frame.pack_forget()
            if not self.choice_frame.winfo_manager():
                self.choice_frame.pack(fill="x", pady=(6, 0), after=self.next_intro)
            self._loading = True
            try:
                for i, (label, box) in enumerate(self.choice_vars):
                    c = n["choices"][i] if i < len(n["choices"]) else {"label": "", "next": ""}
                    if label.get() != c["label"]:
                        label.set(c["label"])
                    box.configure(values=names)
                    box.set(c["next"])
            finally:
                self._loading = False
            return
        self.choice_frame.pack_forget()
        if not self.ways_frame.winfo_manager():
            self.ways_frame.pack(fill="x", after=self.next_intro)
        if not self.other_frame.winfo_manager():
            self.other_frame.pack(fill="x", pady=(12, 0), after=self.ways_frame)
        total = sum(_weight(c["weight"]) for c in n["children"])
        for i, c in enumerate(n["children"]):
            chance = cg.percent(Fraction(_weight(c["weight"]), total)) if total else "-"
            table.insert("", "end", iid=str(i), values=(
                c["next"], c["weight"], chance, capital(describe_cond(c["if"])), c["else"] or ""))
        self._loading = True
        try:
            self.next_box.configure(values=names)
            self.else_box.configure(values=[LEAVE_OUT] + names)
            self.node_else_box.configure(values=[ENDS] + names)
            self.node_else_box.set(n["else"] or ENDS)
            if self.summary_var.get() != n["summary"]:
                self.summary_var.set(n["summary"])
            if self.outcome_var.get() != n["outcome"]:
                self.outcome_var.set(n["outcome"])
            if self.child_index is not None and self.child_index < len(n["children"]):
                table.selection_set(str(self.child_index))
                self._show_child()
            else:
                self.child_index = None
                for var in (self.next_var, self.weight_var):
                    var.set("")
                self.if_box.set("")
                self.else_box.set("")
        finally:
            self._loading = False

    def _child_selected(self, _event=None) -> None:
        if self._loading:
            return
        picked = self.children_table.selection()
        if not picked:
            return
        self.child_index = int(picked[0])
        self._loading = True
        try:
            self._show_child()
        finally:
            self._loading = False

    def select_child(self, index: int) -> None:
        self.child_index = index
        self.show_children_table()

    def _show_child(self) -> None:
        n = self.node()
        c = n["children"][self.child_index]
        if self.next_var.get() != c["next"]:
            self.next_var.set(c["next"])
        if self.weight_var.get() != str(c["weight"]):
            self.weight_var.set(str(c["weight"]))
        options = cond_options(self.g, c["if"])
        self.if_box.configure(values=[w for w, _c in options])
        self.if_box.set(next(w for w, cond in options if cond == c["if"]))
        self.else_box.set(c["else"] or LEAVE_OUT)

    def _child_set(self, key: str, value) -> None:
        n = self.node()
        if self._loading or n is None or self.child_index is None or self.child_index >= len(n["children"]):
            return
        if n["children"][self.child_index][key] == value:
            return
        n["children"][self.child_index][key] = value
        self.changed()
        self._update_child_row()

    def _update_child_row(self) -> None:
        n = self.node()
        total = sum(_weight(c["weight"]) for c in n["children"])
        for i, c in enumerate(n["children"]):
            chance = cg.percent(Fraction(_weight(c["weight"]), total)) if total else "-"
            if self.children_table.exists(str(i)):
                self.children_table.item(str(i), values=(c["next"], c["weight"], chance,
                                                         capital(describe_cond(c["if"])), c["else"] or ""))

    def _weight_changed(self) -> None:
        text = self.weight_var.get().strip()
        try:
            value = int(text)
        except ValueError:
            return
        self._child_set("weight", value)

    def _child_cond_changed(self) -> None:
        n = self.node()
        if n is None or self.child_index is None:
            return
        c = n["children"][self.child_index]
        options = dict(cond_options(self.g, c["if"]))
        c["if"] = options.get(self.if_box.get())
        if c["if"] is None:
            c["else"] = None
        self.changed()
        self.show_children_table()

    def add_child(self) -> None:
        n = self.node()
        if n is None or n["type"] == "question":
            return
        others = [k for k in self.g["nodes"] if k != self.nid]
        n["children"].append({"next": others[-1] if others else "", "weight": 1, "if": None, "else": None})
        self.child_index = len(n["children"]) - 1
        self.changed()
        self.show_children_table()

    def remove_child(self) -> None:
        n = self.node()
        if n is None or self.child_index is None or self.child_index >= len(n["children"]):
            return
        del n["children"][self.child_index]
        self.child_index = None
        self.changed()
        self.show_children_table()

    def _choice_set(self, index: int, key: str) -> None:
        n = self.node()
        if self._loading or n is None or n["type"] != "question":
            return
        while len(n["choices"]) <= index:
            n["choices"].append({"label": "", "next": ""})
        label, box = self.choice_vars[index]
        n["choices"][index][key] = label.get() if key == "label" else box.get()
        self.changed()

    # ---- parts ----

    def add_part(self) -> None:
        n = self.node()
        if n is None:
            return
        if n["type"] == "question":
            SHOW_INFO(TITLE, "The question's ways on are its two buttons: point a button at the new part on the "
                             "Next tab.", parent=self.window)
        new = free_id(self.g)
        self.g["nodes"][new] = blank_node()
        if n["type"] != "question":
            n["children"].append({"next": new, "weight": 1, "if": None, "else": None})
        self.changed()
        self.refresh_now()
        self.select_node(new, "Text")

    def delete_part(self) -> None:
        if self.node() is None:
            return
        if len(self.g["nodes"]) == 1:
            SHOW_INFO(TITLE, "An event needs at least one part.", parent=self.window)
            return
        if not ASK_YES_NO(TITLE, f"Delete the part {self.nid}? The ways on to it go too.", parent=self.window):
            return
        delete_node(self.g, self.nid)
        self.nid = self.g["start"]
        self.changed()
        self.refresh_now()
        self.show_node()

    def rename_part(self) -> None:
        new = self.name_var.get().strip()
        if new == self.nid or self.node() is None:
            return
        if not cg.ID_RE.match(new):
            SHOW_ERROR(TITLE, "A part's name is 1 to 32 letters, digits or _ (no spaces).", parent=self.window)
            return
        if new in self.g["nodes"]:
            SHOW_ERROR(TITLE, f"There is already a part named {new}.", parent=self.window)
            return
        rename_node(self.g, self.nid, new)
        self.nid = new
        self.changed()
        self.refresh_now()
        self.show_node()

    # ---- changes (effects) ----

    def show_effects(self) -> None:
        n = self.node()
        self.effect_list.delete(0, "end")
        self.add_effect_menu.delete(0, "end")
        kinds = effect_kinds(self.g["games"])
        for kind in kinds:
            words = EFFECT_NAMES[kind] + ("  (risky)" if kind in RISKY else "")
            self.add_effect_menu.add_command(label=words, command=lambda k=kind: self.add_effect(k))
        if n is None:
            return
        for e in n["effects"]:
            self.effect_list.insert("end", describe_effect(e))
        if self.effect_index is not None and self.effect_index < len(n["effects"]):
            self.effect_list.selection_set(self.effect_index)
        else:
            self.effect_index = None
        self._effect_form()

    def _effect_selected(self, _event=None) -> None:
        picked = self.effect_list.curselection()
        if picked:
            self.effect_index = picked[0]
            self._effect_form()

    def add_effect(self, kind: str) -> None:
        n = self.node()
        if n is None:
            return
        n["effects"].append(new_effect(kind, self.g["games"]))
        self.effect_index = len(n["effects"]) - 1
        self.changed()
        self.show_effects()

    def remove_effect(self) -> None:
        n = self.node()
        if n is None or self.effect_index is None:
            return
        del n["effects"][self.effect_index]
        self.effect_index = None
        self.changed()
        self.show_effects()

    def move_effect(self, step: int) -> None:
        n = self.node()
        i = self.effect_index
        if n is None or i is None or not 0 <= i + step < len(n["effects"]):
            return
        n["effects"][i], n["effects"][i + step] = n["effects"][i + step], n["effects"][i]
        self.effect_index = i + step
        self.changed()
        self.show_effects()

    def _effect_changed(self) -> None:
        n = self.node()
        if n is None or self.effect_index is None:
            return
        self.effect_list.delete(self.effect_index)
        self.effect_list.insert(self.effect_index, describe_effect(n["effects"][self.effect_index]))
        self.effect_list.selection_set(self.effect_index)
        self.changed()

    def _effect_form(self) -> None:
        form = self.effect_form
        for child in form.winfo_children():
            child.destroy()
        n = self.node()
        if n is None or self.effect_index is None or self.effect_index >= len(n["effects"]):
            self.effect_warning.configure(text="")
            return
        e = n["effects"][self.effect_index]
        do = e["do"]
        self.effect_warning.configure(text=RISKY.get(do, ""))
        row = 0

        def var_of(value, kind=tk.StringVar):
            return kind(master=self.window, value=value)

        def integer(key: str, low: int, high: int, label: str) -> None:
            nonlocal row
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = var_of(str(e.get(key, "")))
            ttk.Spinbox(form, from_=low, to=high, textvariable=var, width=12).grid(row=row, column=1, sticky="w")

            def write(*_a):
                try:
                    e[key] = int(var.get())
                except ValueError:
                    return
                self._effect_changed()
            var.trace_add("write", write)
            row += 1

        def flag(key: str, label: str) -> None:
            nonlocal row
            var = var_of(bool(e.get(key)), tk.BooleanVar)

            def write():
                e[key] = bool(var.get())
                self._effect_changed()
            ttk.Checkbutton(form, text=label, variable=var, command=write).grid(row=row, column=0, columnspan=3,
                                                                                sticky="w", pady=2)
            row += 1

        if do in ("food", "tech"):
            integer("amount", -cg.MAX_AMOUNT, cg.MAX_AMOUNT, f"Amount of {cg.UNITS[do]} (below 0 takes):")
            flag("scaled", "Scaled by the Island Events Scale patches, when they are on")
            flag("defer", "Keep it as the award: given later by \"Give the award kept earlier\"")
        elif do == "pay_award":
            ttk.Label(form, text="Gives the award kept earlier on the way to this part.").grid(row=0, column=0,
                                                                                              sticky="w")
            row = 1
        else:
            villagers = [r for r, role in self.g["roles"].items() if role["kind"] == "villager"]
            ttk.Label(form, text="Who:").grid(row=row, column=0, sticky="w", pady=2)
            who = ttk.Combobox(form, state="readonly", width=24, values=[capital(role_words(r)) for r in villagers])
            who.grid(row=row, column=1, sticky="w")
            if e.get("role") in villagers:
                who.current(villagers.index(e["role"]))
            else:
                who.set(str(e.get("role")))

            def pick_who(_e=None):
                e["role"] = villagers[who.current()]
                self._effect_changed()
            who.bind("<<ComboboxSelected>>", pick_who)
            row += 1
            if do == "kill":
                cause = e.get("cause", "custom")
                choice = var_of(cause if cause in CAUSE_WORDS else "own")
                own = var_of("" if cause in CAUSE_WORDS else cause)
                count = ttk.Label(form, text="")

                def write_cause(*_a):
                    words = own.get()
                    count.configure(text=f"{len(words)} of {cg.CAUSE_BYTES}",
                                    foreground=RED if len(words) > cg.CAUSE_BYTES else "")
                    e["cause"] = choice.get() if choice.get() != "own" else words
                    self._effect_changed()
                ttk.Label(form, text="The death is recorded as:").grid(row=row, column=0, sticky="w", pady=(6, 2))
                row += 1
                for key, words in CAUSE_WORDS.items():
                    ttk.Radiobutton(form, text=words, value=key, variable=choice, command=write_cause).grid(
                        row=row, column=0, columnspan=3, sticky="w")
                    row += 1
                ttk.Radiobutton(form, text=OWN_WORDS, value="own", variable=choice, command=write_cause).grid(
                    row=row, column=0, sticky="w")
                ttk.Entry(form, textvariable=own, width=48).grid(row=row, column=1, sticky="w")
                count.grid(row=row, column=2, sticky="w", padx=(6, 0))
                own.trace_add("write", lambda *_a: (choice.set("own"), write_cause()))
                row += 1
            elif do == "status":
                ttk.Label(form, text="Becomes a Heathen (New Believers only).").grid(row=row, column=0,
                                                                                    columnspan=3, sticky="w")
                row += 1
            elif do == "health":
                integer("min", 1, cg.HEALTH_MAX, "Health from:")
                integer("max", 1, cg.HEALTH_MAX, "to (the same for an exact value):")
            elif do == "preference":
                ttk.Label(form, text="Adds to:").grid(row=row, column=0, sticky="w", pady=2)
                which = ttk.Combobox(form, state="readonly", width=12, values=["likes", "dislikes"])
                which.grid(row=row, column=1, sticky="w")
                which.set(e.get("list") or "likes")
                row += 1
                ttk.Label(form, text="The like or dislike:").grid(row=row, column=0, sticky="w", pady=2)
                word = ttk.Combobox(form, state="readonly", width=24, values=common(self.g["games"], "preferences"))
                word.grid(row=row, column=1, sticky="w")
                word.set(e.get("preference") or "")
                row += 1

                def write_pref(_e=None):
                    e["list"], e["preference"] = which.get(), word.get()
                    self._effect_changed()
                which.bind("<<ComboboxSelected>>", write_pref)
                word.bind("<<ComboboxSelected>>", write_pref)
            elif do == "skill":
                ttk.Label(form, text="One of these skills, at random:").grid(row=row, column=0, sticky="w", pady=2)
                row += 1
                boxes = ttk.Frame(form)
                boxes.grid(row=row, column=0, columnspan=3, sticky="w")
                row += 1
                for i, skill in enumerate(common(self.g["games"], "skills")):
                    var = var_of(skill in (e.get("skills") or []), tk.BooleanVar)

                    def write_skill(s=skill, v=var):
                        skills = [x for x in e.get("skills") or [] if x != s]
                        if v.get():
                            skills.append(s)
                        e["skills"] = skills
                        self._effect_changed()
                    ttk.Checkbutton(boxes, text=skill, variable=var, command=write_skill).grid(
                        row=0, column=i, sticky="w", padx=(0, 8))
                integer("min", 1, cg.SKILL_ADD_MAX, "Gains from:")
                integer("max", 1, cg.SKILL_ADD_MAX, "to:")

    # ---- roles ----

    def show_roles(self) -> None:
        table = self.roles_table
        table.delete(*table.get_children())
        for r, role in self.g["roles"].items():
            villager = role["kind"] == "villager"
            sex = (VILLAGER_SEX if villager else STRANGER_SEX).get(role["sex"], role["sex"])
            table.insert("", "end", iid=r, values=(
                capital(role_words(r)), KIND_WORDS[role["kind"]].split(" (")[0],
                ("No" if role.get("optional") else "Yes") if villager else "-", sex,
                role.get("min_age", "-") if villager else "-"))
        if self.role_id in self.g["roles"]:
            table.selection_set(self.role_id)
        self._role_form()

    def _role_selected(self, _event=None) -> None:
        picked = self.roles_table.selection()
        if picked and picked[0] != self.role_id:
            self.role_id = picked[0]
            self._role_form()

    def _role_changed(self) -> None:
        self.changed()
        self._build_insert_menu()
        r = self.role_id
        role = self.g["roles"][r]
        villager = role["kind"] == "villager"
        sex = (VILLAGER_SEX if villager else STRANGER_SEX).get(role["sex"], role["sex"])
        self.roles_table.item(r, values=(capital(role_words(r)), KIND_WORDS[role["kind"]].split(" (")[0],
                                         ("No" if role.get("optional") else "Yes") if villager else "-", sex,
                                         role.get("min_age", "-") if villager else "-"))

    def _role_form(self) -> None:
        form = self.role_form
        for child in form.winfo_children():
            child.destroy()
        r = self.role_id
        if r not in self.g["roles"]:
            return
        role = self.g["roles"][r]
        ttk.Label(form, text=capital(role_words(r)), font=self.fonts["label"]).grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Who:").grid(row=1, column=0, sticky="w", pady=2)
        kind = ttk.Combobox(form, state="disabled" if r == "subject" else "readonly", width=36,
                            values=list(KIND_WORDS.values()))
        kind.grid(row=1, column=1, sticky="w")
        kind.set(KIND_WORDS[role["kind"]])

        def set_kind(_e=None):
            new = next(k for k, v in KIND_WORDS.items() if v == kind.get())
            if new == role["kind"]:
                return
            self.g["roles"][r] = ({"kind": "stranger", "sex": "random"} if new == "stranger" else new_role())
            self._role_changed()
            self._role_form()
        kind.bind("<<ComboboxSelected>>", set_kind)
        sexes = VILLAGER_SEX if role["kind"] == "villager" else STRANGER_SEX
        ttk.Label(form, text="Man or woman:").grid(row=2, column=0, sticky="w", pady=2)
        sex = ttk.Combobox(form, state="readonly", width=36, values=list(sexes.values()))
        sex.grid(row=2, column=1, sticky="w")
        sex.set(sexes.get(role["sex"], ""))

        def set_sex(_e=None):
            role["sex"] = next(k for k, v in sexes.items() if v == sex.get())
            self._role_changed()
        sex.bind("<<ComboboxSelected>>", set_sex)
        if role["kind"] != "villager":
            return
        age = tk.StringVar(master=self.window, value=str(role["min_age"]))
        ttk.Label(form, text="Youngest age (years):").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=0, to=80, textvariable=age, width=6).grid(row=3, column=1, sticky="w")

        def set_age(*_a):
            try:
                role["min_age"] = int(age.get())
            except ValueError:
                return
            self._role_changed()
        age.trace_add("write", set_age)
        special = "; ".join(f"{g.name}: {g.special}" for n, g in cg.GAMES.items() if n in self.g["games"])
        flags = [("optional", "The event can happen without this villager (leave the box empty if it is needed)",
                  r != "subject"),
                 ("exclude_nursing", "Never a mother or father nursing a baby", True),
                 ("exclude_special", f"Never a special villager ({special})", True),
                 ("believers_only", "New Believers: believers only (never a Heathen)", True)]
        for i, (key, words, enabled) in enumerate(flags):
            var = tk.BooleanVar(master=self.window, value=bool(role.get(key)))

            def write(k=key, v=var):
                role[k] = bool(v.get())
                self._role_changed()
            box = ttk.Checkbutton(form, text=words, variable=var, command=write,
                                  state="normal" if enabled else "disabled")
            box.grid(row=4 + i, column=0, columnspan=2, sticky="w", pady=2)

    def add_role(self) -> None:
        name = ASK_STRING(TITLE, "A short name for the new role (letters, digits or _; e.g. rival):",
                          parent=self.window)
        if not name:
            return
        name = name.strip()
        if not cg.ID_RE.match(name) or name in self.g["roles"]:
            SHOW_ERROR(TITLE, "A role's name is 1 to 32 letters, digits or _, and not one already used.",
                       parent=self.window)
            return
        self.g["roles"][name] = new_role()
        self.role_id = name
        self.changed()
        self.show_roles()
        self._build_insert_menu()

    def remove_role(self) -> None:
        r = self.role_id
        if r is None or r == "subject":
            SHOW_INFO(TITLE, "The main villager is always part of the event.", parent=self.window)
            return
        if not ASK_YES_NO(TITLE, f"Remove the role {r}? Text and changes that name it will show as problems.",
                          parent=self.window):
            return
        del self.g["roles"][r]
        self.role_id = "subject"
        self.changed()
        self.show_roles()
        self._build_insert_menu()

    # ---- the Check tab ----

    def show_problems(self) -> None:
        box = self.problem_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        for tag in box.tag_names():
            if tag.startswith("p"):
                box.tag_delete(tag)
        if not self.problems:
            box.insert("end", "No problems.")
            self.check_status.configure(text="No problems: the game can play this event.", foreground=GREEN)
        else:
            self.check_status.configure(text=f"{len(self.problems)} problem(s): the game will not list this event "
                                             "until they are fixed.", foreground=RED)
            for i, problem in enumerate(self.problems):
                start = box.index("end-1c")
                box.insert("end", plain_problem(problem) + ("\n" if i < len(self.problems) - 1 else ""))
                tag = f"p{i}"
                box.tag_add(tag, start, f"{start} lineend")
                box.tag_bind(tag, "<Button-1>", lambda _e, i=i: self.jump_to_problem(i))
        box.configure(state="disabled")

    def jump_to_problem(self, index: int) -> str | None:
        nid = problem_node(self.problems[index], self.g["nodes"]) if index < len(self.problems) else None
        if nid is not None:
            self.select_node(nid, "Text")
        return nid

    def show_chances(self) -> None:
        names = [cg.GAMES[n].name for n in self.g["games"]]
        current = self.chance_game.get()
        self.chance_game.configure(values=names)
        if current not in names:
            self.chance_game.set(names[0] if names else "")
        wanted = [("patch", p) for p in self.g["patches"]] + \
                 [("role", r) for r, role in self.g["roles"].items() if role.get("optional")]
        if list(self.chance_vars) != wanted:
            for child in self.chance_picks.winfo_children():
                child.destroy()
            old = self.chance_vars
            self.chance_vars = {}
            for key in wanted:
                var = tk.BooleanVar(master=self.window, value=old[key].get() if key in old else key[0] == "role")
                words = f"with {patch_words(key[1])} on" if key[0] == "patch" else f"with {role_words(key[1])}"
                ttk.Checkbutton(self.chance_picks, text=words, variable=var, command=self.show_chances).pack(
                    side="left", padx=(0, 8))
                self.chance_vars[key] = var
        game = next((n for n in self.g["games"] if cg.GAMES[n].name == self.chance_game.get()), None)
        if game is None:
            text = "Tick at least one game on the Event tab."
        else:
            patches = [k[1] for k, v in self.chance_vars.items() if k[0] == "patch" and v.get()]
            roles = [r for r, role in self.g["roles"].items()
                     if not role.get("optional") or (self.chance_vars.get(("role", r)) and
                                                     self.chance_vars[("role", r)].get())]
            text = chances_text(self.g, game, patches, roles)
        box = self.chances_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def chances_shown(self) -> str:
        return self.chances_box.get("1.0", "end-1c")

    # ---- the library ----

    def game(self) -> int:
        return self.game_numbers[max(0, self.game_box.current())]

    def save_folder(self) -> Path | None:
        index = self.folder_box.current()
        return self.folders[index] if 0 <= index < len(self.folders) else None

    def find_folders(self) -> None:
        title = self.titles[max(0, self.game_box.current())]
        try:
            self.folders = vv_save_backup.find_save_folders(title, self.documents) if self.documents else []
        except OSError:
            self.folders = []
        self.folder_box.configure(values=[str(f) for f in self.folders])
        if self.folders:
            self.folder_box.current(0)
        else:
            self.folder_box.set(NO_FOLDER)
        self.list_library()

    def list_library(self) -> None:
        events = library_events(self.save_folder(), self.scrolling.get())
        self.library = [stem for stem, _n in events]
        self.event_box.configure(values=[stem + (f"  ({n} problem(s))" if n else "") for stem, n in events])
        if events:
            pick = self.library.index(self.stem) if self.stem in self.library else 0
            self.event_box.current(pick)
        else:
            self.event_box.set(NO_EVENTS)

    def _leave_changes(self) -> bool:
        return not self.dirty or ASK_YES_NO(TITLE, "This event has changes that are not saved. Leave them?",
                                            parent=self.window)

    def new(self) -> None:
        if self._leave_changes():
            self.load_event(new_event(), None, dirty=True)

    def new_from_example(self) -> None:
        if self._leave_changes():
            self.load_event(example_event(), None, dirty=True)

    def new_from_cave(self) -> None:
        if self._leave_changes():
            self.load_event(example_event(CAVE_EXAMPLE), None, dirty=True)

    def open_selected(self) -> None:
        folder = self.save_folder()
        index = self.event_box.current()
        if folder is None or index < 0 or index >= len(self.library):
            SHOW_INFO(TITLE, "Choose an event in the library first.", parent=self.window)
            return
        if not self._leave_changes():
            return
        stem = self.library[index]
        try:
            g = read_event(cg.library_folder(folder) / (stem + cg.GRAPH_SUFFIX))
        except (OSError, ValueError) as exc:
            SHOW_ERROR(TITLE, f"{stem} cannot be opened: {exc}", parent=self.window)
            return
        self.load_event(g, stem)

    def _write(self, stem: str) -> Saved | None:
        folder = self.save_folder()
        if folder is None:
            SHOW_ERROR(TITLE, "No save folder was found for this game, so there is no library to save in. Use "
                              "Export to keep the event as a file.", parent=self.window)
            return None
        try:
            saved = save_event(self.g, folder, stem, self.scrolling.get())
        except (OSError, ValueError) as exc:
            SHOW_ERROR(TITLE, f"The event could not be saved: {exc}", parent=self.window)
            return None
        self.stem = stem
        self.dirty = False
        self.list_library()
        self.refresh_now()
        note = "" if self.game() in self.g["games"] else (
            f" It is not made for {cg.GAMES[self.game()].name}, so this game will not list it.")
        if saved.problems:
            self.status.configure(text=f"Saved {stem}, but the game will not list it until the problems on the "
                                       f"Check tab are fixed.{note}", foreground=RED)
        elif note:
            self.status.configure(text=f"Saved {stem}.{note}", foreground=RED)
        else:
            self.status.configure(text=f"Saved {stem}: the game lists it.", foreground=GREEN)
        return saved

    def save(self) -> Saved | None:
        if self.stem is None:
            return self.save_as()
        return self._write(self.stem)

    def save_as(self, name: str | None = None) -> Saved | None:
        if name is None:
            name = ASK_STRING(TITLE, "Save the event in the library as:", parent=self.window,
                              initialvalue=self.stem or cg.library_stem(self.g["title"]))
        if not name:
            return None
        stem = cg.library_stem(name)
        folder = self.save_folder()
        if folder is not None and stem != self.stem and \
                (cg.library_folder(folder) / (stem + cg.GRAPH_SUFFIX)).exists() and \
                not ASK_YES_NO(TITLE, f"{stem} is already in the library. Replace it?", parent=self.window):
            return None
        return self._write(stem)

    def duplicate(self) -> None:
        copy = json.loads(json.dumps(self.g))
        title = copy["title"]
        copy["title"] = (title[:cg.TITLE_BYTES - 5] + " copy") if title else "A copy"
        self.load_event(copy, None, dirty=True)
        self.status.configure(text="A copy, not saved yet: Save gives it a name of its own.", foreground="")

    def delete(self) -> None:
        folder = self.save_folder()
        if folder is None or self.stem is None:
            SHOW_INFO(TITLE, "Open an event from the library to delete it.", parent=self.window)
            return
        paths = [p for p in (cg.library_folder(folder) / (self.stem + cg.GRAPH_SUFFIX),
                             cg.library_folder(folder) / (self.stem + cg.BINARY_SUFFIX)) if p.exists()]
        if not paths:
            return
        if not ASK_YES_NO(TITLE, f"Move {self.stem} to the Recycle Bin? It can be put back from there.",
                          parent=self.window):
            return
        try:
            vv_translations.recycle(paths, shell=RECYCLE_SHELL)
        except OSError as exc:
            SHOW_ERROR(TITLE, f"{self.stem} was left in place: {exc}", parent=self.window)
            return
        gone = self.stem
        self.stem = None
        self.dirty = True
        self.list_library()
        self.refresh_now()
        self.status.configure(text=f"{gone} was moved to the Recycle Bin. The event stays open here, not saved.",
                              foreground="")

    def import_event(self) -> None:
        if not self._leave_changes():
            return
        path = ASK_OPEN(parent=self.window, title="Import a Custom Island Event",
                        filetypes=[("Custom Island Events", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            g = read_event(Path(path))
        except (OSError, ValueError) as exc:
            SHOW_ERROR(TITLE, f"That file is not a Custom Island Event: {exc}", parent=self.window)
            return
        self.load_event(g, None, dirty=True)
        self.status.configure(text="Imported: Save keeps it in this game's library.", foreground="")

    def export_event(self) -> Path | None:
        path = ASK_SAVE(parent=self.window, title="Export this Custom Island Event", defaultextension=".json",
                        initialfile=(self.stem or cg.library_stem(self.g["title"])) + ".json",
                        filetypes=[("Custom Island Events", "*.json")])
        if not path:
            return None
        try:
            write_atomic(Path(path), event_json(self.g))
        except OSError as exc:
            SHOW_ERROR(TITLE, f"The event could not be exported: {exc}", parent=self.window)
            return None
        self.status.configure(text=f"Exported to {path}.", foreground="")
        return Path(path)

    def close(self) -> None:
        if not self._leave_changes():
            return
        self._closed = True
        if self._job is not None:
            try:
                self.window.after_cancel(self._job)
            except tk.TclError:
                pass
        self.window.destroy()
