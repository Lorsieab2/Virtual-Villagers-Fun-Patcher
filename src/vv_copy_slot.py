"""Copy Player Slot: copy one save slot's village into an empty slot of the same save folder.

The owner's request: "build the Copy to Player slot in the Virtual Villagers patcher".  The player picks a
slot that has a village and an empty slot, types a name, and the empty slot gets the same village under the
new name -- with every file the patcher keeps for it -- so both can be played from then on.

What one slot is (all five games; docs/rename-tribe.md, measured on the five stock executables and the
owner's saves, read only)
    * The game's own files: the slot save "<stem><S>.ldw" and the two older generations the game rotates
      before every save, "<stem>2<S>.ldw" and "<stem>4<S>.ldw" (never read back by the game).  The slot
      list "<stem>0.ldw" is shared: each slot's name in a fixed-width field and one "in use" byte per slot
      (A New Home and The Lost Children: names at 22, 33 bytes each, the bytes at 187; The Secret City: 22 /
      21 / 127; The Tree of Life and New Believers: 34 / 21 / 139).  At startup every game loads each
      slot's save and rewrites the list from what loads (A New Home 0x41D260, The Secret City 0x4285E0), so
      a slot is in use exactly when its save is there.
    * The tribe's name is in the save buffer (A New Home and The Lost Children +0x8, The Secret City
      +0x12ECC, The Tree of Life +0x170B8, New Believers +0x17D14) and in the slot list.  There is no
      checksum.  The name rule is Rename Tribe's (vv_tribe_rename.name_problem).
    * The patcher's own files of the slot: everything in "Virtual Villagers Fun Patcher\\Save <S>\\" (its
      Logs and Data), the older layout's "Virtual Villagers Fun Patcher Logs\\Save <S>\\" and every
      "... - Save <S>.<ext>" in the patcher's folders, the oldest builds' "<stem>_<S>.dat" beside the saves,
      and the Family Tree Maker's saved trees of the village ("<tribe> (Save <S>) Family Tree.vvtree").

What is copied, and what changes in the copy
    Every one of those files gets a copy for the target slot, "Save <S>" / " - Save <S>" / "(Save <S>)"
    in its path becoming the target's.  The source's files are never changed.  Where a copy's CONTENT
    names the slot or the village, the copy is made to name the target (src/vv_copy_slot.py
    `_transform`): the slot field of every binary file that keeps one (Parentage Records, the logs'
    cross-check and repair-approval markers, the arrival and birth markers, Paid Purchases, Story
    Purchases, the Island Event Timer, The Secret City's Fruit Tree Timers and Second Faction, The Lost
    Children's Elder Totems files, with their own checksums made again); the village ids those markers
    keep (FNV-1a of the "Village: <name> (Save <S>)" line); the logs' "Village: <name> (Save <S>)" lines of
    this village; Log Decisions; and the Like and Dislike Words boundaries of every copied log.  Files the
    game binds by roster or fingerprint (graves, rosters, masks, titles, looks...) are copied byte for byte.
    Every copy keeps its original's file times: several files are believed only while the slot's save
    was written after them.

    NOT copied: the older builds' SHARED logs (no slot in their path; records of every village of the
    game, told apart by their headers), the Backups folder, "Copies Made Before Repairs", any "*.tmp", and
    an older generation of the source that is another village's or already exists for the target.

Safety
    * The game must be closed (it rewrites the slot list when it quits).  Nothing here pauses or closes a
      game.
    * The source must be a readable save of this game; the target must have no save; no file this copy
      would make may exist already (nothing is ever written over).  Only the slot list's target field and
      byte are changed in a file that was there before.
    * Before anything is written the whole save folder is backed up with Back Up Saves' own copier,
      labelled "(before copy)".
    * Every file is written to a temporary file and then moved into place (a new file with a rename that
      fails if the name was taken meanwhile; the slot list with os.replace), and read back.
    * Afterwards the copied save is read with the patcher's own readers (the tribe name, and every villager
      vv_last_names finds, which must be the source's), and it must equal the source byte for byte except
      the name.  Any failure removes every file and folder this copy made and puts the slot list and the
      shared Like and Dislike Words files back as they were.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests drive it against throwaway save
folders and a fake process list.
"""
from __future__ import annotations

import json
import os
import re
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_backup
import vv_save_layout as layout
import vv_tribe_rename as rename
from vv_game_text import GAME_TEXT  # the games' bytes: Windows-1252, every byte kept

BACKUP_LABEL = vv_save_backup.BEFORE_COPY
SLOTS = rename.SLOTS
# The slot list's "in use" byte of slot 1, per game (docs/rename-tribe.md; read on the owner's lists).
FLAG_OFFSET = {1: 187, 2: 187, 3: 127, 4: 139, 5: 139}

SAVES = layout.SAVES                       # "Virtual Villagers Fun Patcher"
LOGS = layout.LOGS                         # "Virtual Villagers Fun Patcher Logs"
DATA = layout.DATA                         # "Virtual Villagers Fun Patcher Data"
TREES = layout.TREES                       # "Virtual Villagers Fun Patcher Family Trees"
LEGACY_LOGS = "VVFP Logs"
PATCHER_FOLDERS = tuple(f.casefold() for f in (LOGS, DATA, TREES, LEGACY_LOGS))
_LEGACY_TOP = re.compile(r"^(vv1_masks|vv1_doublers|vv1_parents|vv2_masks|vvfp_masks)_([1-5])\.dat$", re.I)
_TOP_STATISTICS = re.compile(r"^Village Statistics - Save ([1-5])\.txt$", re.I)
# A pending Repair Saves & Logs approval (crosscheck_bridge.h): the owner chose "Original only" -- the copy
# starts with no repair waiting to run.
_APPROVAL = re.compile(r" Repair Approved - Save [1-5]\.dat$", re.I)
# Set-aside and before-repair copies the companions and the repairs keep beside a file: not the slot's
# data, never read as it; not copied.
_CLUTTER = (".another-village-", ".before-", ".unreadable-")


def _clutter(name: str) -> bool:
    low = name.casefold()
    return any(mark in low for mark in _CLUTTER)

# Binary files that keep the slot as a little-endian dword: their first bytes -> where the slot is.
_SLOT_FIELD = {
    b"VP02": 8,     # A New Home's Parentage Records (vv1_parentage.c)
    b"VXC1": 12,    # A New Home's log cross-check marker (vv1_crosscheck.inc)
    b"VRA1": 12,    # Repair Approved (crosscheck_bridge.h)
    b"VCA1": 12,    # Arrivals Recorded (arrival_backfill.h)
    b"VCB1": 12,    # Births Recorded
    b"VPP1": 12,    # Paid Purchases (paid_purchases.h)
    b"VSQ1": 12,    # Story Purchases (story_queue.inc)
    b"VITK": 12,    # Island Event Timer (island_timer_keep.h)
    b"VV3T": 12,    # The Secret City's Fruit Tree Timers (vv3_fruit_timers.h)
    b"VV2F": 12,    # The Secret City's Second Faction (vvfp_vv3_both_factions.c)
}
# Where a marker keeps its village id (FNV-1a of "Village: <name> (Save <S>)"), and its length then.
_VILLAGE_ID = {b"VXC1": (44, 48), b"VCA1": (16, 20), b"VCB1": (16, 20)}
TOTEMS_MAGIC = b"VVFP VV2 TOTEMS\0"
PENDING_MAGIC = b"VVFP VV2 PENDING"


class CopyError(Exception):
    """A copy that was refused or failed, with a reason a player can read."""


class GameRunning(CopyError):
    """The game that uses this save folder is running."""


# ---------------------------------------------------------------------------
# The slots
# ---------------------------------------------------------------------------


@dataclass
class Slots:
    sources: list[rename.SlotInfo]       # slots holding a village this tool can copy
    targets: list[int]                   # empty slots (no save)
    unreadable: list[rename.SlotInfo]    # slots with a save this tool cannot read
    every: list[rename.SlotInfo] = field(default_factory=list)   # all five, in order

    def label(self, slot: int) -> str:
        """How the "Copy to" list names a slot: empty, or the village it would overwrite."""
        if slot in self.targets:
            return f"Save {slot}: (empty)"
        info = next((i for i in self.every if i.slot == slot), None)
        name = info.name if info is not None and info.name is not None else "(a save this tool cannot read)"
        return f"Save {slot}: {name} (will be overwritten)"


def read_slots(game: rename.GameSaves, folder: Path) -> Slots:
    """Which slots can be copied from, and which are empty.  The game sees "<stem><N>.ldw" as player slot
    N (the owner, 2026-11-01): a slot is empty exactly when that file is not there and holds a player when
    it is, whatever the slot list "<stem>0.ldw" says."""
    sources, targets, unreadable = [], [], []
    every = rename.read_slots(game, Path(folder))
    for info in every:
        path = game.save_path(Path(folder), info.slot)
        if not os.path.lexists(path):
            targets.append(info.slot)
        elif info.name is not None:
            sources.append(info)
        else:
            unreadable.append(info)
    return Slots(sources, targets, unreadable, every)


def copy_folders(title: str, documents: Path | None) -> list[Path]:
    """The save folders offered: Rename Tribe's (the patched games' "<title> - Modded..." folders)."""
    return rename.rename_folders(title, documents)


# ---------------------------------------------------------------------------
# Where each file goes
# ---------------------------------------------------------------------------


def _fnv1a32(text: str) -> int:
    h = 2166136261
    for byte in text.encode(GAME_TEXT, "replace"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return h or 1


def _rename_slot_in_name(name: str, source: int, target: int) -> str:
    """" - Save <S>" (the last one directly before an extension or the end) and "(Save <S>)" made the
    target's."""
    found = list(re.finditer(rf" - Save {source}(?=\.|$)", name, re.I))
    if found:
        at = found[-1]
        name = name[:at.start()] + f" - Save {target}" + name[at.end():]
    return re.sub(rf"\(Save {source}\)", f"(Save {target})", name, flags=re.I)


def target_relative(relative: Path, source: int, target: int) -> Path | None:
    """Where the target's copy of the patcher file ``relative`` goes, or None when it is not the source
    slot's own (or is never copied)."""
    parts = relative.parts
    if not parts:
        return None
    name = parts[-1]
    if name.casefold().endswith(".tmp") or any(p.casefold() == layout.COPIES.casefold() for p in parts):
        return None
    if _clutter(name) or _APPROVAL.search(name):
        return None
    top = parts[0].casefold()
    # Output-only exports (the Family Tree Maker's reports and pictures, the Matchmaker's report; an older
    # build's "Logs\Genealogy"): made again from the logs whenever they are wanted, so not copied.  The
    # saved trees are the copy's: `_plan_trees`.
    if top == TREES.casefold() or (top == LOGS.casefold() and len(parts) >= 2
                                   and parts[1].casefold() == "genealogy"):
        return None
    if len(parts) == 1:
        match = _LEGACY_TOP.match(name)
        if match and int(match.group(2)) == source:
            return Path(f"{match.group(1)}_{target}.dat")
        match = _TOP_STATISTICS.match(name)
        if match and int(match.group(1)) == source:
            return Path(f"Village Statistics - Save {target}.txt")
        return None
    # Everything of one save in one folder, and the older layout's slot folder of logs: all of it.
    if top in (SAVES.casefold(), LOGS.casefold()) and len(parts) >= 3 \
            and parts[1].casefold() == f"save {source}":
        rest = list(parts[2:])
        rest[-1] = _rename_slot_in_name(rest[-1], source, target)
        return Path(parts[0], f"Save {target}", *rest)
    if top in (SAVES.casefold(), LOGS.casefold()) and re.fullmatch(r"save [1-5]", parts[1].casefold()):
        return None                                 # another slot's folder
    if top not in PATCHER_FOLDERS:
        return None
    renamed = _rename_slot_in_name(name, source, target)
    if renamed == name or not re.search(rf" - Save {target}(?=\.|$)", renamed, re.I):
        return None
    return Path(*parts[:-1], renamed)


# ---------------------------------------------------------------------------
# What changes inside a copy
# ---------------------------------------------------------------------------


@dataclass
class LogMap:
    """How a copied log's byte offsets moved when its village lines were rewritten."""
    changes: list[tuple[int, int, int]] = field(default_factory=list)   # (start, old length, new length)

    def offset(self, value: int) -> int:
        moved = value
        for start, old, new in self.changes:
            if value >= start + old:
                moved += new - old
            elif value > start:
                moved += min(value - start, new) - (value - start)
        return moved


# Numbered records are numbered per GAME across every slot (native/shared/log_slot.h): "Conception <n>",
# "Birth <n>", "Death <n>", "Arrived <n>", "Island event <n>", "Unaccounted <n>", "Repair <n>".  A record's
# own number opens its line; other lines refer to records by the same words ("Checked: Death 53's cause",
# "- Birth 288 says ...", an answered question).  The owner chose "Renumber the copy": the copy's records
# get new numbers after the game's highest of each kind, in their order, and every reference follows.
NUMBERED = ("Conception", "Birth", "Death", "Arrived", "Island event", "Unaccounted", "Repair")
_KINDS = "|".join(re.escape(k) for k in NUMBERED)
_MARKER = re.compile(rf"^({_KINDS}) (\d+)(?=\s|$)")
# A reference: the words at a line's start or after a space, a bracket or a quote -- never glued to a word
# ("Dislikes:Conception 1" is a like/dislike word, not a record).
_REFERENCE = re.compile(rf"(?<![^\s(\"'])({_KINDS}) (\d+)\b")


# Lines that name a village, never a record: a header, a rename note, the reconciliation report's
# "Save <S>: <name>".  A tribe may be named "Birth 3"; such a line is never renumbered.
_IDENTITY_LINE = re.compile(r"^(?:Village: |Tribe renamed from |Save [1-5]: )")


def record_numbers(data: bytes) -> dict[str, set[int]]:
    """Every record number that opens a line of ``data``, by kind."""
    found: dict[str, set[int]] = {}
    for line in data.decode(GAME_TEXT).splitlines():
        match = _MARKER.match(line)
        if match:
            found.setdefault(match.group(1), set()).add(int(match.group(2)))
    return found


def highest_numbers(folder: Path) -> dict[str, int]:
    """The game's highest number of each kind, in every log of the save folder (every slot's, the shared
    ones and an older build's folders alike; never the Backups)."""
    highest: dict[str, int] = {}
    for path in Path(folder).rglob("*.txt"):
        try:
            parts = path.relative_to(folder).parts
        except ValueError:
            continue
        if parts and parts[0].casefold() == vv_save_backup.BACKUPS_FOLDER.casefold():
            continue
        try:
            numbers = record_numbers(path.read_bytes())
        except OSError:
            continue
        for kind, values in numbers.items():
            highest[kind] = max(highest.get(kind, 0), max(values))
    return highest


def renumbering(copied: list[bytes], highest: dict[str, int]) -> dict[str, dict[int, int]]:
    """Each kind's old number -> new number for the records the copy holds: after the game's highest of
    that kind, in the records' own order."""
    olds: dict[str, set[int]] = {}
    for data in copied:
        for kind, values in record_numbers(data).items():
            olds.setdefault(kind, set()).update(values)
    return {kind: {old: highest.get(kind, 0) + 1 + i for i, old in enumerate(sorted(values))}
            for kind, values in olds.items()}


def renumber_text(text: str, numbers: dict[str, dict[int, int]]) -> str:
    """Every record reference in ``text`` given its new number (strings of Log Decisions)."""
    def swap(match: re.Match) -> str:
        new = numbers.get(match.group(1), {}).get(int(match.group(2)))
        return match.group(0) if new is None else f"{match.group(1)} {new}"
    return _REFERENCE.sub(swap, text)


def slot_swapped(header: str, source: int, target: int) -> str:
    """"Village: <name> (Save <S>)" with only its LAST "(Save <S>)" made the target's (log_slot.h reads the
    last one)."""
    marker = f" (Save {source})"
    at = header.rfind(marker)
    return header if at < 0 else header[:at] + f" (Save {target})" + header[at + len(marker):]


def header_map(headers: set[str], current: str, new_header: str, source: int, target: int) -> dict[str, str]:
    """What each of the village's header lines becomes in the copy.  The copy must read exactly like the
    source (the live check of The Secret City, renamed "KT N" -> "Kalahuna Tribe 3: N": its Deaths log kept
    the OLD header, which the save-time reconcile, statistics_reconcile.inc, never counts because it matches
    the CURRENT header exactly).  So only the current header gets the new name; a header of an older name
    keeps that name, its slot made the target's."""
    return {h: (new_header if h == current else slot_swapped(h, source, target)) for h in headers}


_NOTE = re.compile(r"^(Tribe renamed from .+ to )(.+?)( on \d{4}-\d{2}-\d{2})( \(Save [1-5]\))?\s*$")


def note_rewrite(text: str, old: str, new: str, source: int, target: int) -> str | None:
    """A "Tribe renamed from <A> to <current> on <date>" note (village_rename.h) made to end at the copy's
    name, so the copy's renames chain back through the same older names as the source's; a note's
    " (Save <S>)" (the shared Village History's) made the target's.  None when ``text`` is no such note."""
    match = _NOTE.match(text)
    if match is None:
        return None
    to = new if match.group(2) == old else match.group(2)
    slot = match.group(4) or ""
    if slot == f" (Save {source})":
        slot = f" (Save {target})"
    rewritten = match.group(1) + to + match.group(3) + slot
    return None if rewritten == text.rstrip() else rewritten


def rewrite_log(data: bytes, headers, new_header: str,
                numbers: dict[str, dict[int, int]] | None = None,
                lines: dict[str, str] | None = None,
                note: tuple[str, str, int, int] | None = None) -> tuple[bytes, LogMap]:
    """The log with each line that is one of ``headers`` (this village's "Village: <name> (Save <S>)")
    made what ``headers`` maps it to (a set: all of them ``new_header``), each "Tribe renamed" note made the
    copy's (``note``: old name, new name, source, target), each line that is a key of ``lines`` made its
    value (the Reconciliation report's "Save <S>: <name>"), and every record number of ``numbers`` given its
    new one; every other byte as it was.  The map moves an offset of ``data`` to the same place in the
    result."""
    mapped = headers if isinstance(headers, dict) else {h: new_header for h in headers}
    out = bytearray()
    mapping = LogMap()
    at = 0
    for line in data.splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        ending = line[len(body):]
        text = body.decode(GAME_TEXT)
        whole = mapped.get(text.rstrip(" \t"))
        if whole is None:
            whole = (lines or {}).get(text)
        if whole is None and note is not None and text.startswith(rename.RENAME_PREFIX):
            whole = note_rewrite(text, *note)
        if whole is not None:
            replaced = whole.encode(GAME_TEXT, "replace")
            mapping.changes.append((at, len(body), len(replaced)))
            out += replaced + ending
        elif numbers and not _IDENTITY_LINE.match(text):
            last = 0
            for match in _REFERENCE.finditer(text):
                new = numbers.get(match.group(1), {}).get(int(match.group(2)))
                if new is None:
                    continue
                digits = str(new)
                out += text[last:match.start(2)].encode(GAME_TEXT)
                out += digits.encode("ascii")
                mapping.changes.append((at + match.start(2), match.end(2) - match.start(2), len(digits)))
                last = match.end(2)
            out += text[last:].encode(GAME_TEXT) + ending
        else:
            out += line
        at += len(line)
    return bytes(out), mapping


# ---------------------------------------------------------------------------
# The older builds' SHARED logs: the village's own records in them
# ---------------------------------------------------------------------------
#
# Before every save had its own folder of logs, every village of the game wrote one shared
# "Virtual Villagers Fun Patcher Logs\<the log's folder>\" (log_slot.h), each record under its village's
# "Village: <name> (Save <S>)" line; every reader still reads them first, keeping only its own village's
# records.  A copy takes its village's records out of them (only those under the village's own lines,
# with any "Tribe renamed" note followed, and a Village History snapshot's "=== ... ===" line with its
# snapshot) into the copy's own "...Logs\Save <T>\<the log's folder>\<the same name>", which every reader
# of slot <T> reads first.  The shared logs themselves are never changed.

_HISTORY_MARK = "=== "
# (the shared folder an older build named it, the newest name): only these folders hold village records.
_SHARED_FOLDERS = {
    "births and conceptions": "Births and Conceptions",
    "deaths and disappearances": "Deaths and Disappearances",
    "deaths": "Deaths and Disappearances",
    "island events": "Island Events",
    "unaccounted villagers": "Unaccounted Villagers",
    "repairs made": "Repairs Made",
    "repairs": "Repairs Made",
    "tribe history": "Tribe History",
    "tribe population": "Tribe Population",
}
_OLDER_NAMES = {"deaths", "repairs"}


def village_ranges(data: bytes, headers: set[str]) -> list[tuple[int, int]]:
    """The byte ranges of ``data`` (a shared log) that are the village's: from each of its "Village:" lines
    (or the "=== ... ===" line opening that Village History snapshot) to the next village's."""
    import vv_tribe_rename as names

    lines = data.splitlines(keepends=True)
    owners: list[str | None] = []
    current: str | None = None
    for i, line in enumerate(lines):
        text = line.rstrip(b"\r\n").decode(GAME_TEXT).rstrip(" \t")
        if text.startswith("Village: "):
            current = text
            if i and owners and lines[i - 1].decode(GAME_TEXT).startswith(_HISTORY_MARK):
                owners[i - 1] = current
        elif current is not None and text.startswith(names.RENAME_PREFIX):
            owners.append(current)
            current = names.apply_rename_note(current, text)
            continue
        owners.append(current)
    ranges: list[tuple[int, int]] = []
    at = 0
    for line, owner in zip(lines, owners):
        end = at + len(line)
        if owner in headers:
            if ranges and ranges[-1][1] == at:
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((at, end))
        at = end
    return ranges


_HEADER = re.compile(r"^Village: (.*) \(Save ([1-5])\)\s*$")


def shared_log_names(folder: Path, slot: int) -> set[str]:
    """Every village name the older SHARED logs keep records under for ``slot`` -- a header's own name, and
    each name a "Tribe renamed" note under it gives it -- counting only blocks that hold a record.  Those
    files are never changed, so a copy into ``slot`` must not take one of these names: every reader would
    take that earlier village's records for the copy's own history."""
    import vv_tribe_rename as names

    found: set[str] = set()
    shared = Path(folder) / LOGS
    try:
        subs = [p for p in shared.iterdir() if p.is_dir() and p.name.casefold() in _SHARED_FOLDERS]
    except OSError:
        return found
    for sub in subs:
        try:
            files = [p for p in sub.iterdir() if p.is_file() and p.name.casefold().endswith(".txt")
                     and not re.search(r"Save [1-5]", p.name) and not _clutter(p.name)]
        except OSError:
            continue
        for path in files:
            try:
                text = path.read_bytes().decode(GAME_TEXT)
            except OSError:
                continue
            header: str | None = None
            block: set[str] = set()
            records = False
            for line in text.splitlines() + ["Village: "]:      # the last block closed like the others
                if line.startswith("Village: "):
                    if header is not None and records:
                        found.update(block)
                    match = _HEADER.match(line.rstrip())
                    header, records = None, False
                    block = set()
                    if match and int(match.group(2)) == slot:
                        header = line.rstrip()
                        block = {match.group(1)}
                    continue
                if header is None:
                    continue
                if line.startswith(names.RENAME_PREFIX):
                    renamed = names.apply_rename_note(header, line.rstrip())
                    if renamed != header:
                        header = renamed
                        new = _HEADER.match(renamed)
                        if new:
                            block.add(new.group(1))
                elif _MARKER.match(line):
                    records = True
    return found


def name_taken_message(name: str, slot: int) -> str:
    return (f"{name} was the name of the village being replaced in Save {slot}, and its old records still use "
            "it. Please choose another name.")


def older_name_taken_message(source_name: str, older: str, slot: int) -> str:
    return (f"{source_name}'s older name {older} was also used by the village being replaced in Save {slot}, "
            f"and its old records still use it, so the copy can't go into Save {slot}. Choose another slot.")


def _record_ranges(data: bytes) -> list[tuple[int, int]]:
    """Each numbered record of ``data``: from its own line to the next record or village line."""
    starts = []
    at = 0
    for line in data.splitlines(keepends=True):
        text = line.decode(GAME_TEXT)
        if _MARKER.match(text) or text.startswith("Village: "):
            starts.append((at, bool(_MARKER.match(text))))
        at += len(line)
    out = []
    for k, (start, numbered) in enumerate(starts):
        if numbered:
            out.append((start, starts[k + 1][0] if k + 1 < len(starts) else len(data)))
    return out


@dataclass
class Piece:
    """Part of a copied log: the bytes of ``ranges`` of a source file, in order."""
    relative: Path
    data: bytes
    ranges: list[tuple[int, int]]

    def text(self) -> bytes:
        return b"".join(self.data[a:b] for a, b in self.ranges)

    def offset(self, value: int) -> int:
        """Where an offset of the source file is in this piece's text."""
        out = 0
        for a, b in self.ranges:
            if value >= b:
                out += b - a
            elif value > a:
                out += value - a
        return out

    @property
    def size(self) -> int:
        return sum(b - a for a, b in self.ranges)


def _patch_dword(data: bytearray, at: int, old: int, new: int) -> bool:
    if len(data) >= at + 4 and struct.unpack_from("<I", data, at)[0] == old:
        struct.pack_into("<I", data, at, new)
        return True
    return False


def transform_binary(data: bytes, source: int, target: int, ids: dict[int, int],
                     old_name: str, new_name: str) -> bytes:
    """A binary sidecar made the target's: its slot field, its village id, The Lost Children's Elder
    Totems files (slot, village name, checksum).  Anything else, or a file that is not whole, as it was."""
    import vv_vv2_totem_store as totems

    out = bytearray(data)
    head = bytes(out[:4])
    if head in _SLOT_FIELD:
        if not _patch_dword(out, _SLOT_FIELD[head], source, target):
            return data                              # another slot's file kept here: left as it is
        place = _VILLAGE_ID.get(head)
        if place is not None and len(out) == place[1]:
            (current,) = struct.unpack_from("<I", out, place[0])
            if current in ids:              # the id of the header line it was for, as the copy has that line
                struct.pack_into("<I", out, place[0], ids[current])
        return bytes(out)
    if out[:16] in (TOTEMS_MAGIC, PENDING_MAGIC) and len(out) >= 48:
        if struct.unpack_from("<I", out, len(out) - 4)[0] != totems._fnv1a(bytes(out[:-4])):
            return data                              # not whole: the game sets it aside either way
        if not _patch_dword(out, 24, source, target):
            return data
        if out[:16] == TOTEMS_MAGIC and struct.unpack_from("<I", out, 16)[0] == 2 \
                and len(out) >= totems.HEADER + 4:
            cap = totems.VILLAGE_CAP
            field_ = bytes(out[totems.HEADER_V1:totems.HEADER_V1 + cap])
            if field_.split(b"\0", 1)[0].decode(GAME_TEXT) == old_name:
                raw = new_name.encode(GAME_TEXT, "replace")[:cap - 1]
                out[totems.HEADER_V1:totems.HEADER_V1 + cap] = raw + bytes(cap - len(raw))
        struct.pack_into("<I", out, len(out) - 4, totems._fnv1a(bytes(out[:-4])))
        return bytes(out)
    return data


def transform_decisions(data: bytes, headers, new_header: str,
                        numbers: dict[str, dict[int, int]] | None = None) -> bytes:
    """Log Decisions: each decision of this village filed under the target's village line, and every
    record it names ("Birth 288 says ...") given the record's new number."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return data
    if not isinstance(doc, dict) or not isinstance(doc.get("decisions"), list):
        return data

    def renumbered(value):
        if isinstance(value, str):
            return renumber_text(value, numbers) if numbers else value
        if isinstance(value, list):
            return [renumbered(v) for v in value]
        if isinstance(value, dict):
            return {k: renumbered(v) for k, v in value.items()}
        return value

    changed = False
    kept = []
    for d in doc["decisions"]:
        if isinstance(d, dict) and d.get("village") in headers:
            village = headers[d["village"]] if isinstance(headers, dict) else new_header
            # The record numbers in what the decision says; never in the village it is filed under (a
            # tribe may be named "Birth 3": its header is an identity, not a record reference).
            new = {k: (village if k == "village" else renumbered(v)) for k, v in d.items()}
        else:
            new = d
        changed = changed or new != d
        kept.append(new)
    if not changed:
        return data
    return json.dumps({**doc, "decisions": kept}, indent=1).encode("utf-8")


def transform_words(data: bytes, source: int, target: int, maps: dict[str, LogMap]) -> bytes:
    """A save's own Like and Dislike Words file: every boundary of a log in the source's own folder
    made the target's log's (its key, and its offset as the rewritten log has it)."""
    prefix = f"{SAVES}\\Save {source}\\".casefold()
    out = []
    for line in data.decode("utf-8", "replace").splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        offset, tab, key = body.partition("\t")
        if tab and key.casefold().startswith(prefix):
            new_key = f"{SAVES}\\Save {target}\\" + key[len(prefix):]
            try:
                value = int(offset)
            except ValueError:
                out.append(line)
                continue
            mapping = maps.get(key.casefold())
            if mapping is not None:
                value = mapping.offset(value)
            out.append(f"{value}\t{new_key}{ending}")
        else:
            out.append(line)
    return "".join(out).encode("utf-8")


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass
class NewFile:
    path: Path                     # where the copy goes (must not exist)
    data: bytes
    source: Path                   # the file it is a copy of (its times are kept)
    kind: str                      # "save", "generation", "file"


@dataclass
class WordsAppend:
    path: Path                     # a shared Like and Dislike Words file
    line: bytes


@dataclass
class Plan:
    game: rename.GameSaves
    folder: Path
    source: int
    target: int
    old_name: str
    new_name: str
    index_before: bytes
    index_after: bytes
    files: list[NewFile] = field(default_factory=list)
    words: list[WordsAppend] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)        # what was not copied, and why
    source_villagers: list[int] = field(default_factory=list)
    renumbered: dict[str, int] = field(default_factory=dict)  # records given a new number, by kind
    removals: list[Path] = field(default_factory=list)      # the target slot's files, removed after the backup
    overwritten: str | None = None                          # the village overwritten ("" unreadable), None: empty


def _relative_key(relative: Path) -> str:
    return "\\".join(relative.parts)


def _plan_trees(plan: Plan, headers: set[str], game: rename.GameSaves) -> None:
    """The Family Tree Maker's saved trees of this village (its game, slot and tribe), named for the target."""
    from vv_genealogy_window import tree_file_name

    folder = plan.folder / TREES
    try:
        trees = sorted(p for p in folder.glob("*.vvtree") if p.is_file())
    except OSError:
        return
    for path in trees:
        if f"(Save {plan.source})".casefold() not in path.name.casefold():
            continue
        try:
            original = path.read_bytes()
            tree = json.loads(original.decode("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(tree, dict) or (tree.get("game"), tree.get("slot"), tree.get("tribe")) != (
                game.number, plan.source, plan.old_name):
            continue
        # The tree the Family Tree Maker opens for the tribe and slot gets the name it opens for the copy
        # (its own tree_file_name: a name may hold characters Windows refuses in a file name, "A/B",
        # "A:B"); any other tree keeps its own name with the slot changed.  Inside, the tribe is as typed.
        if path.name.casefold() == tree_file_name(plan.old_name, plan.source).casefold():
            name = tree_file_name(plan.new_name, plan.target)
        else:
            name = _rename_slot_in_name(path.name, plan.source, plan.target)
        data = json.dumps({**tree, "slot": plan.target, "tribe": plan.new_name}, indent=1).encode("utf-8")
        plan.files.append(NewFile(folder / name, data, path, "file"))


# ---------------------------------------------------------------------------
# The target slot's leftovers
# ---------------------------------------------------------------------------
#
# The owner (2026-11-01): "for all games please acknowledge empty slots/New Players!!!! (the game sees
# (game name)1-5.ldw as player slots)".  A slot is empty exactly when "<stem><N>.ldw" is not there,
# whatever the slot list says.  Such a slot may still hold an earlier village's files: the game's older
# generations "<stem>2<N>.ldw" / "<stem>4<N>.ldw" and everything the patcher kept for Save <N>.  A copy into
# it removes them -- the owner's explicit rule for a copy target, as Start Over does for its slot -- only
# after the "(before copy)" backup holds every one of them, and the player sees the list before saying Yes.
# Which files are the slot's follows Start Over's wipe (native/shared/save_reset.c, "START OVER WIPES THE
# WHOLE SAVE"): the save's own folder and the older layout's "...Logs\Save <N>" (all but pictures and the
# ".before-..." repair copies), every patcher file whose name says " - Save <N>" (of this game), the oldest
# builds' "<name>_<N>.dat", and the Family Tree Maker's files of that save (a .vvtree by the save it
# records, the rest by "(Save <N>)" / " - Save <N>").  Backups and "Copies Made Before Repairs" are never
# entered; nothing outside slot <N> is ever touched.

_PICTURES = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
_KEPT_FOLDERS = ("backups", layout.COPIES.casefold())


def _name_slot(name: str, trees: bool) -> int:
    """save_reset.c wipe_name_slot: the save a name says it is of; 0 none, -1 two different ones."""
    found = 0
    pattern = r" - Save (\d)(?=\.|$" + (r"| )" if trees else r")")
    said = [int(m.group(1)) for m in re.finditer(pattern, name, re.I)]
    if trees:
        said += [int(m.group(1)) for m in re.finditer(r"\(Save (\d)\)", name, re.I)]
    for s in said:
        if found and found != s:
            return -1
        found = s
    return found


def _name_game(name: str) -> int:
    match = re.match(r"Virtual Villagers ([1-5]) ", name, re.I)
    return int(match.group(1)) if match else 0


def _tree_record(path: Path) -> tuple[int, int] | None:
    try:
        tree = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(tree, dict) or not isinstance(tree.get("slot"), int) or not 1 <= tree["slot"] <= 5:
        return None
    game = tree.get("game")
    return (game if isinstance(game, int) else 0), tree["slot"]


def slot_files(game: rename.GameSaves, folder: Path, slot: int) -> list[Path]:
    """Every file of slot ``slot`` (see above), sorted: its save when it has one (a slot being overwritten,
    the owner: "I want the Copy Player slot to be able to overwrite existing slots"), its older generations
    and every patcher file of that save -- for an empty slot, what an earlier village left there."""
    folder = Path(folder)
    out: list[Path] = []
    if game.save_path(folder, slot).is_file():
        out.append(game.save_path(folder, slot))
    for generation in rename.GENERATIONS:
        path = game.generation_path(folder, generation, slot)
        if path.is_file():
            out.append(path)

    def kept(name: str) -> bool:
        low = name.casefold()
        return low.endswith(_PICTURES) or ".before-" in low

    def walk(root: Path):
        if not root.is_dir() or vv_save_backup._is_link(root):
            return
        for entry in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            if vv_save_backup._is_link(entry):
                continue
            if entry.is_dir():
                if entry.name.casefold() not in _KEPT_FOLDERS:
                    yield from walk(entry)
            elif entry.is_file():
                yield entry

    for root in (folder / SAVES / f"Save {slot}", folder / LOGS / f"Save {slot}"):
        out += [p for p in walk(root) if not kept(p.name)]
    for root in (folder / DATA, folder / LOGS):
        for path in walk(root):
            rel = path.relative_to(folder).parts
            if rel[0].casefold() == LOGS.casefold() and (re.fullmatch(r"(?i)save [1-5]", rel[1])
                                                        or rel[1].casefold() == "genealogy"):
                continue
            if kept(path.name) or _name_game(path.name) not in (0, game.number):
                continue
            if _name_slot(path.name, trees=False) == slot:
                out.append(path)
    for root in (folder / TREES, folder / LOGS / "Genealogy"):
        for path in walk(root):
            name = path.name
            if kept(name) or _name_game(name) not in (0, game.number):
                continue
            said = _name_slot(name, trees=True)
            if name.casefold().endswith((".vvtree", ".vvtree.tmp")):
                record = _tree_record(path)
                if record is None or record[0] not in (0, game.number) or (said and said != record[1]):
                    continue                     # its save cannot be told: kept, as Start Over keeps it
                if record[1] == slot:
                    out.append(path)
            elif said == slot:
                out.append(path)
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if not entry.is_file():
            continue
        match = _LEGACY_TOP.match(entry.name)
        top = _TOP_STATISTICS.match(entry.name)
        if (match and int(match.group(2)) == slot) or (top and int(top.group(1)) == slot):
            out.append(entry)
    unique: dict[str, Path] = {}
    for path in out:
        unique.setdefault(str(path).casefold(), path)
    return sorted(unique.values(), key=lambda p: str(p).casefold())


slot_leftovers = slot_files


def _stale_boundaries(folder: Path, game: int, checker, plan: Plan) -> list[WordsAppend]:
    """A Like and Dislike Words line for every log of the older layout whose name a leftover log had
    (log_words.h: the LAST line naming a file counts, so a leftover's boundary would apply to the copy's
    log, or to a later one of that name): the copy's log gets its own (all of it old words when its source
    had none, as the source was), a leftover the copy does not replace gets 0 (nothing old)."""
    import vv_move_to_save_folders as mover

    written = {line.line.decode("utf-8").split("\t", 1)[1].strip().casefold() for line in plan.words}
    made = {_relative_key(f.path.relative_to(plan.folder)).casefold(): f for f in plan.files}
    out: list[WordsAppend] = []
    for path in plan.removals:
        rel = path.relative_to(folder)
        if rel.parts[0].casefold() != LOGS.casefold() or not path.name.casefold().endswith(".txt"):
            continue
        key = checker.word_key(_relative_key(rel))
        if key.casefold() in written:
            continue
        try:
            stale = mover._boundary(folder, game, key)
        except OSError:
            stale = None
        if stale is None:
            continue
        copy = made.get(_relative_key(rel).casefold())
        value = len(copy.data) if copy is not None else 0
        out.append(WordsAppend(layout.words_file_for(folder, game, key), f"{value}\t{key}\r\n".encode("utf-8")))
        written.add(key.casefold())
    return out


def plan_copy(game: rename.GameSaves, folder: Path, source: int, target: int, new_name: str) -> Plan:
    """Everything the copy would write, worked out and checked before anything is written."""
    import vv_last_names as ln

    folder = Path(folder)
    if source not in SLOTS or target not in SLOTS:
        raise CopyError("A save slot is 1 to 5.")
    if source == target:
        raise CopyError("Choose two different slots.")
    problem = rename.name_problem(game, new_name)
    if problem is not None:
        raise CopyError(problem)
    save = game.save_path(folder, source)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise CopyError(f"Save {source} has no tribe ({save.name} is missing).") from exc
    except OSError as exc:
        raise CopyError(f"Could not read {save.name}: {exc}") from exc
    old = rename.save_name(game, data)
    save_layout = rename._save_layout(game, data)
    if old is None or save_layout is None:
        raise CopyError(f"{save.name} is not a {game.title} save this tool can read.")
    try:
        villagers = ln._entries(game.number, data)
    except Exception as exc:  # noqa: BLE001 -- any reader failure means the save is not one to copy
        raise CopyError(f"The villagers in {save.name} could not be read ({exc}), so nothing was copied.") from exc
    destination = game.save_path(folder, target)
    if os.path.lexists(destination) and not destination.is_file():
        raise CopyError(f"{destination.name} is not a file, so Save {target} cannot be copied over.")
    overwritten = None
    if destination.is_file():
        try:
            overwritten = rename.save_name(game, destination.read_bytes()) or ""
        except OSError as exc:
            raise CopyError(f"Could not read {destination.name}: {exc}") from exc
    index_file = game.index_path(folder)
    try:
        index = index_file.read_bytes()
    except OSError as exc:
        raise CopyError(f"Could not read the slot list {index_file.name}: {exc}") from exc
    flag = FLAG_OFFSET[game.number] + target - 1
    if rename.index_name(game, index, target) is None or flag >= len(index):
        raise CopyError(f"The slot list {index_file.name} is not one this tool can read.")
    after = bytearray(rename._with_name(index, game.index_offset(target), game.index_stride, new_name))
    after[flag] = 1
    # The older shared logs are never changed: a name an earlier village of the target slot keeps records
    # under there would make every reader take those records for the copy's own history.
    taken = shared_log_names(folder, target)
    if new_name in taken:
        raise CopyError(name_taken_message(new_name, target))
    # ...and the source's OLDER names keep their headers in the copy, as "(Save <T>)": one the target
    # slot's earlier village also has records under there would mix the two villages the same way.
    for header in sorted(rename._village_names(game, folder, source, old)):
        match = _HEADER.match(header)
        if match and match.group(1) != old and match.group(1) in taken:
            raise CopyError(older_name_taken_message(old, match.group(1), target))
    plan = Plan(game, folder, source, target, old, new_name, index, bytes(after), source_villagers=villagers)
    plan.overwritten = overwritten
    try:
        plan.removals = slot_leftovers(game, folder, target)
    except OSError as exc:
        raise CopyError(f"Could not list the save folder: {exc}") from exc
    name_at = save_layout[0] + game.name_offset
    plan.files.append(NewFile(destination, rename._with_name(data, name_at, game.save_field, new_name), save, "save"))
    for generation in rename.GENERATIONS:
        older = game.generation_path(folder, generation, source)
        mine = game.generation_path(folder, generation, target)
        try:
            older_data = older.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise CopyError(f"Could not read {older.name}: {exc}") from exc
        older_layout = rename._save_layout(game, older_data)
        if older_layout is None or rename.save_name(game, older_data) != old:
            plan.skipped.append(f"{older.name}: another village's or not a save, so not copied")
            continue
        plan.files.append(NewFile(
            mine, rename._with_name(older_data, older_layout[0] + game.name_offset, game.save_field, new_name),
            older, "generation"))

    headers = rename._village_names(game, folder, source, old)
    new_header = rename.village_header(new_name, target)
    mapped = header_map(headers, rename.village_header(old, source), new_header, source, target)
    ids = {_fnv1a32(h): _fnv1a32(mapped[h]) for h in headers}
    note = (old, new_name, source, target)
    try:
        relatives = vv_save_backup.files_to_back_up(folder)
    except OSError as exc:
        raise CopyError(f"Could not list the save folder: {exc}") from exc

    # Every log of the copy, as the pieces it is made of (a slot log: the whole file; a log of the older
    # layout's slot folder: the village's records from the shared logs first, as every reader reads them,
    # then the slot's own file of that name).
    texts: dict[str, tuple[Path, list[tuple[int, Piece]]]] = {}

    def add_text(destination: Path, rank: int, piece: Piece) -> None:
        key = _relative_key(destination).casefold()
        texts.setdefault(key, (destination, []))[1].append((rank, piece))

    others: list[tuple[Path, Path, bytes]] = []
    words_own: list[tuple[Path, Path]] = []          # (source relative, copy relative)
    for relative in relatives:
        new_relative = target_relative(relative, source, target)
        if new_relative is None:
            continue
        path = folder / relative
        if layout.is_words_file(path) and relative.parts[0].casefold() == SAVES.casefold():
            words_own.append((relative, new_relative))
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise CopyError(f"Could not read {relative}: {exc}") from exc
        if relative.name.casefold().endswith(".txt"):
            add_text(new_relative, 2, Piece(relative, raw, [(0, len(raw))]))
        else:
            others.append((relative, new_relative, raw))
    _plan_shared_logs(folder, source, target, headers, relatives, add_text)

    # The copy's records renumbered after the game's highest of each kind (log_slot.h numbers per game).
    import vv_log_tools as tools
    checker = tools.load_checker()
    assembled: dict[str, bytes] = {}
    normalised: set[str] = set()
    for key, (destination, pieces) in texts.items():
        pieces.sort(key=lambda item: item[0])
        _drop_older_duplicates(pieces)
        if len(pieces) > 1 and game.number in checker.WORD_FIXES:
            # One file keeps one like/dislike boundary (log_words.h), but its pieces may each have had
            # their own: each piece's older words are put right first, with the checker's own list
            # (as Repair Saves & Logs does), so the whole file is the game's words and its boundary is 0.
            _normalise_words(folder, game.number, checker, pieces)
            normalised.add(key)
        assembled[key] = b"".join(piece.text() for _rank, piece in pieces)
    numbers = renumbering(list(assembled.values()), highest_numbers(folder))
    plan.renumbered = {kind: len(values) for kind, values in numbers.items()}
    recon = {f"Save {source}: {old}": f"Save {target}: {new_name}"}

    maps: dict[str, LogMap] = {}
    for key, (destination, pieces) in texts.items():
        data, mapping = rewrite_log(assembled[key], mapped, new_header, numbers, recon, note)
        first = pieces[0][1]
        plan.files.append(NewFile(folder / destination, data, folder / first.relative, "file"))
        if destination.parts[0].casefold() == SAVES.casefold():
            maps[_relative_key(first.relative).casefold()] = mapping       # its own words file: below
        elif key in normalised:
            words_key = checker.word_key(_relative_key(destination))
            plan.words.append(WordsAppend(layout.words_file_for(folder, game.number, words_key),
                                          f"0\t{words_key}\r\n".encode("utf-8")))
        else:
            plan.words += _shared_boundary(folder, game.number, checker, destination, pieces, mapping)
    for relative, new_relative, raw in others:
        if re.search(r" Log Decisions - Save \d\.json$", relative.name, re.I):
            raw = transform_decisions(raw, mapped, new_header, numbers)
        elif relative.name.casefold().endswith(".json"):
            pass
        else:
            raw = transform_binary(raw, source, target, ids, old, new_name)
        plan.files.append(NewFile(folder / new_relative, raw, folder / relative, "file"))
    for relative, new_relative in words_own:
        path = folder / relative
        plan.files.append(NewFile(folder / new_relative, transform_words(path.read_bytes(), source, target, maps),
                                  path, "file"))
    _plan_trees(plan, headers, game)
    plan.words += _stale_boundaries(folder, game.number, checker, plan)
    # Every place the copy writes must be free once the slot's leftovers are gone; a leftover of the other
    # layout that the games would prefer (per_save.h) is one of those leftovers.  Anything else in the way
    # is not slot <T>'s alone, so nothing is ever written over it.
    removing = {str(p).casefold() for p in plan.removals}
    taken = [f.path for f in plan.files if os.path.lexists(f.path) and str(f.path).casefold() not in removing]
    taken += [p for p in _older_counterparts(folder, [f.path for f in plan.files])
              if str(p).casefold() not in removing]
    if taken:
        shown = "; ".join(str(p.relative_to(folder)) for p in taken[:8])
        more = f" and {len(taken) - 8} more" if len(taken) > 8 else ""
        raise CopyError(
            f"Save {target} has no player, but these files the copy would write are already there and are not "
            f"Save {target}'s alone: {shown}{more}. Nothing is ever written over, so nothing was copied.")
    names = [str(f.path).casefold() for f in plan.files]
    if len(names) != len(set(names)):
        raise CopyError("Two of the slot's files would be copied to the same place, so nothing was copied.")
    return plan


def _plan_shared_logs(folder: Path, source: int, target: int, headers: set[str], relatives: list[Path],
                      add_text) -> None:
    """The village's records in the older builds' shared logs, for the copy's "...Logs\\Save <T>\\" folder
    (see above).  Only the folders of village records; files named for a slot are copied by their name."""
    shared = Path(folder) / LOGS
    own_population = any(
        len(r.parts) >= 4 and r.parts[0].casefold() in (SAVES.casefold(), LOGS.casefold())
        and r.parts[1].casefold() == f"save {source}" and "tribe population" in (p.casefold() for p in r.parts)
        for r in relatives)
    try:
        subs = sorted((p for p in shared.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
    except OSError:
        return
    for sub in subs:
        newest = _SHARED_FOLDERS.get(sub.name.casefold())
        if newest is None or (newest == "Tribe Population" and own_population):
            continue
        rank = 0 if sub.name.casefold() in _OLDER_NAMES else 1
        try:
            files = sorted((p for p in sub.iterdir() if p.is_file()), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for path in files:
            name = path.name
            if not name.casefold().endswith(".txt") or re.search(r"Save [1-5]", name) or _clutter(name):
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise CopyError(f"Could not read {path.relative_to(folder)}: {exc}") from exc
            ranges = village_ranges(data, headers)
            if not ranges:
                continue
            if newest == "Tribe Population":
                # A Village Population page is one village's, its header on its second line: the whole page.
                villages = {l.decode(GAME_TEXT).rstrip(" \t\r\n") for l in data.splitlines()
                            if l.startswith(b"Village: ")}
                if not villages <= headers:
                    continue
                ranges = [(0, len(data))]
            add_text(Path(LOGS, f"Save {target}", newest, name), rank,
                     Piece(path.relative_to(folder), data, ranges))


def _drop_older_duplicates(pieces: list[tuple[int, Piece]]) -> None:
    """A record an older build's folder ("Deaths", "Repairs") keeps word for word in the newer folder too
    is one record, as every reader counts it (scripts/vvfp_consistency_check.py deaths_records): only the
    newer folder's copy is kept."""
    later = [piece.text() for rank, piece in pieces if rank > 0]
    for rank, piece in pieces:
        if rank != 0 or not later:
            continue
        kept = []
        for a, b in piece.ranges:
            cut = a
            for start, end in _record_ranges(piece.data[a:b]):
                block = piece.data[a + start:a + end]
                if any(block in text for text in later):
                    if a + start > cut:
                        kept.append((cut, a + start))
                    cut = a + end
            if b > cut:
                kept.append((cut, b))
        piece.ranges = kept


def _normalise_words(folder: Path, game: int, checker, pieces: list[tuple[int, Piece]]) -> None:
    """Each piece's like/dislike words written with the old list (before its own boundary; all of it when
    its source recorded none -- log_words.h) put right with the checker's own list
    (scripts/vvfp_consistency_check.py WORD_FIXES / WORD_LINE, as old_words and Repair Saves & Logs use
    them).  Each piece then holds only the game's own words."""
    import vv_move_to_save_folders as mover

    fixes = checker.WORD_FIXES.get(game) or {}
    for _rank, piece in pieces:
        text = piece.text()
        try:
            boundary = mover._boundary(folder, game, checker.word_key(_relative_key(piece.relative)))
        except OSError:
            boundary = None
        until = min(piece.offset(boundary), len(text)) if boundary is not None else len(text)
        out, at = [], 0
        for match in checker.WORD_LINE.finditer(text, 0, until):
            word = match.group(2).decode(GAME_TEXT).strip()
            new = fixes.get(word, word)
            if new != word:
                out.append(text[at:match.start(2)])
                out.append(new.encode(GAME_TEXT))
                at = match.end(2)
        out.append(text[at:])
        piece.data = b"".join(out)
        piece.ranges = [(0, len(piece.data))]


def _shared_boundary(folder: Path, game: int, checker, destination: Path, pieces: list[tuple[int, Piece]],
                     mapping: LogMap) -> list[WordsAppend]:
    """The Like and Dislike Words boundary of a copied log of the older layout (its boundaries are in the
    SHARED words file): where its pieces' own boundaries put it.  A source log with no line is all old
    words (log_words.h); a copy none of whose pieces has a line gets none either."""
    import vv_move_to_save_folders as mover

    found = False
    base = 0
    result = None
    for _rank, piece in pieces:
        try:
            boundary = mover._boundary(folder, game, checker.word_key(_relative_key(piece.relative)))
        except OSError:
            boundary = None
        if boundary is not None:
            found = True
        at = piece.offset(boundary) if boundary is not None else piece.size
        if result is None and at < piece.size:
            result = base + at
        base += piece.size
    if not found:
        return []
    key = checker.word_key(_relative_key(destination))
    path = layout.words_file_for(folder, game, key)
    return [WordsAppend(path, f"{mapping.offset(base if result is None else result)}\t{key}\r\n".encode("utf-8"))]


def _older_counterparts(folder: Path, paths: list[Path]) -> list[Path]:
    """For each data file the copy makes, its counterpart under the other layout, when it is there: the
    games read the one written last (per_save.h), so a leftover of a former village there would win."""
    found: list[Path] = []
    for path in paths:
        if layout.is_words_file(Path(path)):
            continue            # the shared Like and Dislike Words file is every save's, never routed
        try:
            relative = "\\".join(Path(path).relative_to(folder).parts)
        except ValueError:
            continue
        candidates: list[str] = []
        older = layout.older_layout(folder, folder / relative)
        if older is not None and older.casefold().startswith(DATA.casefold() + "\\"):
            candidates.append(older)
            renamed = layout.old_name(older)
            if renamed:
                candidates.append(renamed)
        place = layout.per_save_place(relative)
        if place is not None and place[2] == "file":
            candidates.append(place[1])
        for candidate in candidates:
            if os.path.lexists(folder / candidate):
                found.append(folder / candidate)
    return found


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------


@dataclass
class CopyResult:
    folder: Path
    source: int
    target: int
    old_name: str
    new_name: str
    backup: vv_save_backup.BackupResult
    created: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    words: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)        # the target slot's files, set aside
    renumbered: dict[str, int] = field(default_factory=dict)  # records given a new number, by kind
    set_aside: Path | None = None                            # where they are now
    overwritten: str | None = None                           # the village overwritten, None: the slot was empty


@dataclass
class _Done:
    files: list[Path] = field(default_factory=list)
    dirs: list[Path] = field(default_factory=list)
    words: dict = field(default_factory=dict)     # shared words file -> its size before (None: not there)
    index: bool = False
    removed: list = field(default_factory=list)   # (the slot's file, where it was set aside)


# The target slot's files are never deleted (history logs never are): they are MOVED, keeping their
# paths, into "Backups\Replaced by copy <date time> - Save <N> - <village>\".  Inside Backups, which no
# game or patcher reader scans (vv_save_backup BACKUPS_FOLDER; per_save.h never routes it; Start Over never
# enters it), and named so Restore Saves never offers it as a backup (only "Backup <date>..." folders are
# backups, vv_save_backup._BACKUP_NAME; vv3_second_faction looks only in those too).
SET_ASIDE_PREFIX = "Replaced by copy "


def set_aside_folder(folder: Path, when: datetime, slot: int, village: str | None) -> Path:
    """A new folder name in Backups for the target slot's files (never one that is there)."""
    name = "".join(ch for ch in (village or "") if ch not in '\\/:*?"<>|').strip(" .") or "no village"
    base = f"{SET_ASIDE_PREFIX}{when:%Y-%m-%d %H-%M-%S} - Save {slot} - {name}"
    backups = Path(folder) / vv_save_backup.BACKUPS_FOLDER
    for k in range(1, 1000):
        candidate = backups / (base if k == 1 else f"{base} ({k})")
        if not os.path.lexists(candidate):
            return candidate
    raise CopyError(f"Too many folders named {base} in {backups}.")


def _set_aside(plan: Plan, backup: vv_save_backup.BackupResult, aside: Path, done: _Done) -> None:
    """Every file of the target slot moved into ``aside`` (its path kept) -- each only once the verified
    backup is seen to hold it exactly; a move keeps its bytes and times."""
    import hashlib

    copies = {str(Path(c.relative)).casefold(): c for c in backup.files}
    original = {str(Path(r)).casefold(): data for r, data in backup.unpaused_bytes.items()}
    for path in plan.removals:
        relative = path.relative_to(plan.folder)
        copied = copies.get(str(relative).casefold())
        if copied is None:
            raise CopyError(f"{relative} is not in the backup, so nothing was set aside.")
        data = path.read_bytes()
        # The backup's copy was verified against this very content when it was made; a slot save (and The
        # Secret City's faction file) was then set to Paused in the backup, its bytes as copied kept beside.
        before = original.get(str(relative).casefold())
        same = data == before if before is not None else (
            (len(data), hashlib.sha256(data).hexdigest()) == (copied.size, copied.sha256))
        if not same:
            raise CopyError(f"{relative} does not match its copy in the backup, so nothing was set aside.")
        moved = aside / relative
        _make_dirs(moved.parent, done)
        os.rename(path, moved)                      # never over anything; the same disk: bytes and times kept
        done.removed.append((path, moved))
        if moved.read_bytes() != data:
            raise CopyError(f"{relative} did not read back as it was after being set aside.")


def _put_back(path: Path, moved: Path) -> None:
    """A set-aside file moved back to its place, exactly as it was (never over anything)."""
    _make_dirs(path.parent, _Done())
    os.rename(moved, path)


def _refuse_if_running(folder: Path, processes: vv_save_backup.ProcessController) -> None:
    import vv_log_tools as tools
    try:
        tools._refuse_if_running(folder, processes)
    except tools.GameRunning as exc:
        raise GameRunning(str(exc).replace("Repair Saves & Logs never", "Copy Player Slot never")) from exc
    except tools.LogToolError as exc:
        raise CopyError(str(exc)) from exc


def _make_dirs(path: Path, done: _Done) -> None:
    missing = []
    probe = Path(path)
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for folder in reversed(missing):
        folder.mkdir()
        done.dirs.append(folder)


def _temporary(path: Path) -> Path:
    return path.with_name(f"{path.name}.{uuid.uuid4().hex[:12]}.vvfp-copy-tmp")


def _write_new(path: Path, data: bytes, times: tuple[int, int], done: _Done) -> None:
    """A new file through a temporary one; the move into place fails if the name was taken meanwhile, so
    nothing is ever written over.  Its original's times are kept."""
    _make_dirs(path.parent, done)
    temporary = _temporary(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(temporary, ns=times)
        os.rename(temporary, path)                     # never replaces on Windows: FileExistsError
    finally:
        if temporary.exists():
            temporary.unlink()
    done.files.append(path)
    if path.read_bytes() != data:
        raise CopyError(f"{path.name} did not read back as written.")
    if abs(os.stat(path).st_mtime_ns - times[1]) > 2_000_000_000:
        raise CopyError(f"The time of {path.name} could not be kept.")


def _replace(path: Path, data: bytes) -> None:
    temporary = _temporary(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise CopyError(f"{path.name} did not read back as written.")


def _append_words(item: WordsAppend, done: _Done) -> None:
    with layout.words_lock_for(item.path):
        if item.path not in done.words:
            done.words[item.path] = item.path.stat().st_size if item.path.exists() else None
            _make_dirs(item.path.parent, done)
        with open(item.path, "ab") as handle:
            handle.write(item.line)
            handle.flush()
            os.fsync(handle.fileno())


def _roll_back(plan: Plan, done: _Done) -> list[str]:
    """Remove only what this copy made, and put the slot list and shared words files back."""
    problems: list[str] = []
    if done.index:
        try:
            if plan.game.index_path(plan.folder).read_bytes() != plan.index_before:
                _replace(plan.game.index_path(plan.folder), plan.index_before)
        except (OSError, CopyError) as exc:
            problems.append(f"{plan.game.index_path(plan.folder).name}: {exc}")
    for path, size in done.words.items():
        try:
            with layout.words_lock_for(path):
                if size is None:
                    path.unlink(missing_ok=True)
                else:
                    with path.open("r+b") as handle:
                        handle.truncate(size)
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for path in reversed(done.files):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for path, moved in reversed(done.removed):
        try:
            _put_back(path, moved)
        except (OSError, CopyError) as exc:
            problems.append(f"{path.name} (set aside as {moved}): {exc}")
    for folder in reversed(done.dirs):
        try:
            folder.rmdir()
        except OSError as exc:
            problems.append(f"{folder}: {exc}")
    return problems


def verify(plan: Plan) -> None:
    """The copied save read with the patcher's own readers, and the slot list read back."""
    import vv_last_names as ln

    game = plan.game
    source = game.save_path(plan.folder, plan.source).read_bytes()
    copy = game.save_path(plan.folder, plan.target).read_bytes()
    name = rename.save_name(game, copy)
    if name != plan.new_name or vv_save_backup.read_village_name(game.number, game.save_path(plan.folder, plan.target)) != plan.new_name:
        raise CopyError(f"The copied save does not read back with the name {plan.new_name}.")
    header = rename._save_layout(game, copy)[0]
    start, end = header + game.name_offset, header + game.name_offset + game.save_field
    if len(copy) != len(source) or copy[:start] != source[:start] or copy[end:] != source[end:]:
        raise CopyError("The copied save is not the same village as the source.")
    if ln._entries(game.number, copy) != plan.source_villagers:
        raise CopyError("The copied save's villagers do not read back as the source's.")
    index = game.index_path(plan.folder).read_bytes()
    if rename.index_name(game, index, plan.target) != plan.new_name or index[FLAG_OFFSET[game.number] + plan.target - 1] != 1:
        raise CopyError("The slot list does not read back with the new name.")


def copy_slot(
    game: rename.GameSaves,
    folder: Path,
    source: int,
    target: int,
    new_name: str,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
    _fail_after: int | None = None,
    expected_removals: list[Path] | None = None,
) -> CopyResult:
    """Copy the village in ``source`` into the empty ``target`` slot of ``folder`` as ``new_name``.

    Refused (CopyError, nothing changed) when the game is running, the name breaks the game's rule, the
    source cannot be read, the target holds a player, or a file the copy would make is there and is not
    the target slot's leftover.  Otherwise the folder is backed up first, the slot's leftovers
    (`slot_leftovers`) are removed once the backup is seen to hold each one, and the copy is made; on any
    failure everything this copy made is removed again and every leftover put back.  ``expected_removals``
    is the list the player was shown: a different list now refuses the copy.  ``_fail_after`` (tests only)
    makes the copy fail after that many files.
    """
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_copy(game, folder, source, target, new_name)
    if expected_removals is not None and sorted(str(p).casefold() for p in expected_removals) != sorted(
            str(p).casefold() for p in plan.removals):
        raise CopyError(f"Save {target}'s leftover files changed after you confirmed, so nothing was copied. "
                        "Try again to see the list as it is now.")
    try:
        backup = vv_save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise CopyError(f"The backup before copying failed, so nothing was copied. {exc}") from exc
    # The backup took a moment; the game may have been started meanwhile.
    _refuse_if_running(folder, controller)
    done = _Done()
    aside = set_aside_folder(folder, when, target, plan.overwritten) if plan.removals else None
    try:
        if aside is not None:
            _set_aside(plan, backup, aside, done)
        for count, item in enumerate(plan.files):
            if _fail_after is not None and count >= _fail_after:
                raise CopyError("stopped for the test")
            info = item.source.stat()
            _write_new(item.path, item.data, (info.st_atime_ns, info.st_mtime_ns), done)
        for item in plan.words:
            _append_words(item, done)
        index_file = game.index_path(folder)
        if index_file.read_bytes() != plan.index_before:
            raise CopyError(f"{index_file.name} changed while the slot was being copied.")
        done.index = True
        _replace(index_file, plan.index_after)
        verify(plan)
    except Exception as exc:  # noqa: BLE001 -- every failure is rolled back
        problems = _roll_back(plan, done)
        if problems:
            raise CopyError(
                f"The copy failed ({exc}) and these could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}.") from exc
        raise CopyError(
            f"The copy failed ({exc}); everything it made was removed and Save {target} is as it was. "
            f"A backup is in {backup.backup_folder}.") from exc
    return CopyResult(folder, source, target, plan.old_name, new_name, backup,
                      [f.path for f in plan.files], plan.skipped, sorted({w.path for w in plan.words}),
                      list(plan.removals), dict(plan.renumbered), aside, plan.overwritten)
