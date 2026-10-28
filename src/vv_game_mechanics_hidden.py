"""Game Mechanics: the "Hidden keys, clicks and cheats" group, shared by the five games' modules
(src/vv_game_mechanics_hidden_vv<N>.py, each with hidden_facts(village=None)).

The owner (2026-10-27): "PUT IMPORTANT STUFF LIKE HIDDEN KEY COMBOS AND CHEAT CODES IN GAME MECHANICS!!!", "Or places you
can click for random tips and hidden cheats and stuff!!!" and "Please cover in the hidden clicks section: Game tips".

Each game's module lists, as Entry rows:
  KEY      every key the stock game reacts to: the translator's keys, every screen's keys, developer keys;
  CODE     typed codes and name cheats;
  CLICK    every hidden or non-obvious click spot;
  TIP      where the game's tips appear, how one is chosen, and every tip text (as sub-lines);
  PATCHER  the patcher's own keys and clicks, each with its patch and whether it is on or off by default.

THE LABELS (the owner's rules; label() gives them):
  VERIFIED-E  gm.RUNNING -- emulated, or run for real, from a caller the game reaches;
  VERIFIED-C  gm.CODE    -- traced on a live path of the stock exe (or the patcher's own code that runs it), at the
              addresses cited;
  OWNER       gm.OWNER   -- what the owner saw in a game (the owner's rule, 2026-10-27: where the code and a live
              observation disagree, both are written down);
  DEAD        code that never runs in the shipped game (no caller, an event nothing makes, a value nothing reads),
              with the reason; never described as something the player can do.  It is traced in the code, so it
              carries gm.CODE and its text starts DEAD_MARK;
  UNCONFIRMED False      -- anything not proven either way.

THE KEY PATH (all five games, read in each stock exe): the program's SDL event pump (VV1 0x403970, VV2 0x403C00,
VV3 0x404220, VV4 0x404830, VV5 0x4047C0) turns a typed character into a "character" event (type 5) and the keys below
into "command" events (type 6), which the current screen's input slot (its vtable +8) receives.  Mouse events (types
1 to 3) carry only the left button.  Nothing else makes key events (each pump's two posting calls are its only
callers), so a screen's code for any other event type never runs.
"""
from __future__ import annotations

from dataclasses import dataclass

import vv_game_mechanics as gm

HIDDEN = "Hidden keys, clicks and cheats"

E, C, U, O = gm.RUNNING, gm.CODE, False, gm.OWNER
LABELS = {gm.RUNNING: "VERIFIED-E", gm.CLAMP: "VERIFIED-E", gm.CODE: "VERIFIED-C", gm.OWNER: "OWNER"}
DEAD_MARK = "DEAD (never runs): "

KEY, CODE, CLICK, TIP, PATCHER = "key", "code", "click", "tip", "patcher"
KINDS = (KEY, CODE, CLICK, TIP, PATCHER)
HEADINGS = {KEY: "Key", CODE: "Typed code", CLICK: "Click", TIP: "Tips", PATCHER: "Patcher"}

# The command numbers the five games' pumps make (each pump's own "mov eax, <n>"; read by the tests).
COMMAND_KEYS = {1000: "Esc", 1002: "Tab", 1003: "Enter", 1004: "Left arrow", 1005: "Right arrow", 1006: "Up arrow",
                1007: "Down arrow", 1008: "Page Up", 1009: "Page Down", 1010: "Home", 1011: "End", 1012: "Insert",
                1013: "Delete", 1018: "F1", 1019: "F2", 1020: "F3", 1021: "F4", 1022: "F5", 1023: "F6", 1024: "F7",
                1025: "F8", 1026: "F9", 1027: "F10"}


@dataclass(frozen=True)
class Entry:
    """One bullet: its kind, its name (the keys, the spot, the code), what it does, and what stands behind it.
    `subs` are (text, verified) sub-bullets; `dead` marks code that never runs (the text says why); `feature` is
    the patcher patch an entry belongs to."""
    kind: str
    name: str
    text: str
    verified: bool | str
    subs: tuple[tuple[str, bool | str], ...] = ()
    dead: bool = False
    feature: str | None = None


def label_of(verified: bool | str, dead: bool = False) -> str:
    """The owner's label for a line: VERIFIED-E, VERIFIED-C, OWNER, DEAD or UNCONFIRMED."""
    if dead:
        return "DEAD"
    return LABELS.get(verified, gm.UNCONFIRMED)


def label(item) -> str:
    """The label of an Entry, or of a Fact made from one (a DEAD fact's text starts DEAD_MARK)."""
    if isinstance(item, Entry):
        return label_of(item.verified, item.dead)
    return label_of(item.verified, item.text.startswith(DEAD_MARK))


def patch_words(feature: str, default_off: frozenset[str], village: gm.Village | None) -> str:
    """'"<patch>", on by default' -- and, with a village, whether that game has it."""
    words = f"\"{gm.feature_name(feature)}\", {'off' if feature in default_off else 'on'} by default"
    if village is not None and not village.general:
        state = village.has(feature)
        if state is True:
            words += "; in this game"
        elif state is False:
            words += "; not in this game"
    return words


def facts(entries, default_off: frozenset[str] = frozenset(), village: gm.Village | None = None) -> list[gm.Fact]:
    """The group's lines: one bullet an entry ("<Kind>: <name>: <text>"), its sub-bullets under it."""
    out: list[gm.Fact] = []
    for entry in entries:
        head = f"{HEADINGS[entry.kind]}: {entry.name}: "
        if entry.dead:
            head = DEAD_MARK + head
        text = entry.text
        if entry.feature:
            text = f"With the patcher ({patch_words(entry.feature, default_off, village)}): {text}"
        out.append(gm.Fact(HIDDEN, head + text, C if entry.dead else entry.verified))
        for sub, verified in entry.subs:
            out.append(gm.Fact(HIDDEN, sub, verified, sub=True))
    return out


def translator_entry(pump: int) -> Entry:
    """The keys the game hears at all (the same pump in all five games)."""
    return Entry(KEY, "Which keys reach the game", (
        f"the program's event pump ({pump:#x}) hands on Esc, Tab, Enter, the four arrows, Page Up, Page Down, Home, End, "
        "Insert, Delete and F1 to F10 as keys, and every typed character (letters, digits, Space, punctuation; "
        "Backspace too) as a character; F11, F12 and every other key are ignored. Alt+F4 ends the program the same way "
        "as closing its window (it sets the same quit flag). The mouse passes only the left button: right, middle and "
        "wheel clicks do nothing anywhere"), C)


def tip_lines(tips, verified_for, note_for) -> tuple[tuple[str, bool | str], ...]:
    """Sub-lines quoting each tip exactly: '<id>: "<text>"' and where the game asks for it."""
    out = []
    for tip in tips:
        tip_id, text = tip[0], tip[-1]
        note = note_for(tip)
        out.append((f"{tip_id}: \"{text}\"{(' -- ' + note) if note else ''}", verified_for(tip)))
    return tuple(out)


def sites_note(sites) -> str:
    if not sites:
        return ""
    return "asked for at " + ", ".join(f"{site:#x}" for site in sites)
