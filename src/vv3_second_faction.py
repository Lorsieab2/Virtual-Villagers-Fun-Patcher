"""The Secret City's second-faction file, as the patcher's tools must keep it linked to its save.

VV3 Both Factions (native/vvfp_vv3_both_factions, docs/vv3-both-factions.md) keeps the second faction in a
per-save file, one entry per save written with it, each bound to the save by an FNV-1a 64 fingerprint of the
save buffer's first 0x6CDC bytes and the tech points.  A tool that rewrites a save -- Back Up Saves pausing the
backup's copy, Repair's "pause older backups" -- changes the fingerprint (the game clock at buffer 0x57C..0x588
is inside it), so without a matching entry the game loads that save with one faction (the owner, 2026-10-27:
"I restored my tribe from a backup and now I've lost the second faction").  So:

* ``relink`` adds an entry for the rewritten save, copied from the entry of the save it was made from;
* ``recognise`` finds, for a save that has no entry, the game's own copy of it (the slot file or its older
  generations N+20 / N+40, in the save folder or any of its backups) that pauses to exactly these bytes, and
  links the save to that copy's entry -- which brings back the second faction of backups made before the fix.

The file layout is the DLL's (magic 'VV2F', version, game 3, slot, count, then 16 entries, newest last; the
oldest is dropped past 16).  An unreadable or invalid file is never written over.
"""
from __future__ import annotations

import os
import struct
import uuid
from pathlib import Path
from typing import Callable

GAME = 3
MAGIC = 0x46325656                     # 'V' 'V' '2' 'F'
ENTRIES = 16
HEADER = 20
STRIDE = {1: 20, 2: 24}                # version 2 adds the recipes byte and 3 reserved
SAVE_HEADER = 12                       # the "ldwg" header before the save buffer
SAVE_POINTS = 0x6CDC                   # the tech points in the save buffer; the fingerprint covers everything before
PATCHER_FOLDER = "Virtual Villagers Fun Patcher"


def faction_file(folder: Path, slot: int) -> Path:
    """Where the DLL keeps slot ``slot``'s file in the save folder (or a backup of it)."""
    return (folder / PATCHER_FOLDER / f"Save {slot}" / "Data" / "Factions"
            / f"Virtual Villagers 3 Second Faction - Save {slot}.dat")


def fingerprint(save: bytes) -> int | None:
    """The DLL's fingerprint of a save file's bytes, or None when they are too short to be a save."""
    buffer = save[SAVE_HEADER:]
    if len(buffer) < SAVE_POINTS + 4:
        return None
    h = 0xCBF29CE484222325
    for byte in buffer[:SAVE_POINTS + 4]:          # the bytes before the points, then the points themselves
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _read(path: Path) -> tuple[int, int, list[bytes]] | None:
    """(version, slot, entries) of a valid file, or None (missing, unreadable or not one the DLL wrote)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < HEADER:
        return None
    magic, version, game, slot, count = struct.unpack_from("<5I", data, 0)
    stride = STRIDE.get(version)
    if magic != MAGIC or game != GAME or stride is None or count > ENTRIES or len(data) != HEADER + ENTRIES * stride:
        return None
    return version, slot, [data[HEADER + i * stride:HEADER + (i + 1) * stride] for i in range(count)]


def _entry_fp(entry: bytes) -> int:
    lo, hi = struct.unpack_from("<II", entry, 0)
    return (hi << 32) | lo


def entry_for(path: Path, fp: int) -> bytes | None:
    """The file's entry for fingerprint ``fp``, or None."""
    found = _read(path)
    if found is None:
        return None
    for entry in found[2]:
        if _entry_fp(entry) == fp:
            return entry
    return None


def _write(path: Path, version: int, slot: int, entries: list[bytes]) -> None:
    stride = STRIDE[version]
    body = struct.pack("<5I", MAGIC, version, GAME, slot, len(entries)) + b"".join(entries)
    body += b"\0" * (HEADER + ENTRIES * stride - len(body))
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with open(temporary, "xb") as handle:
        handle.write(body)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != body:
        raise OSError(f"{path.name} did not read back as written")


def add_entry(path: Path, fp: int, source: bytes) -> bool:
    """Add an entry for fingerprint ``fp`` with ``source``'s faction, levels and recipes (``source`` is an
    entry of any slot file of the same slot).  False when the file is missing or invalid, or already has it."""
    found = _read(path)
    if found is None:
        return False
    version, slot, entries = found
    if any(_entry_fp(e) == fp for e in entries):
        return False
    stride = STRIDE[version]
    new = struct.pack("<II", fp & 0xFFFFFFFF, fp >> 32) + source[8:stride].ljust(stride - 8, b"\0")
    entries = (entries + [new])[-ENTRIES:]          # newest last, the oldest dropped past 16
    _write(path, version, slot, entries)
    return True


def relink(folder: Path, slot: int, before: bytes, after: bytes) -> bool:
    """After a tool rewrote slot ``slot``'s save in ``folder`` from ``before`` to ``after``: give ``after`` the
    entry ``before`` had.  False when ``before`` had none (no second faction) or nothing changed."""
    old, new = fingerprint(before), fingerprint(after)
    if old is None or new is None or old == new:
        return False
    path = faction_file(folder, slot)
    source = entry_for(path, old)
    return source is not None and add_entry(path, new, source)


def _candidates(save_folder: Path, slot: int, base: str) -> list[Path]:
    """Every copy the game wrote of this slot ("<base><slot>.ldw" and its older generations <slot+20> and
    <slot+40>), in the save folder and in each of its backups, newest backup first."""
    folders = [save_folder]
    backups = save_folder / "Backups"
    if backups.is_dir():
        folders += sorted((p for p in backups.iterdir() if p.is_dir()), reverse=True)
    return [folder / f"{base}{number}.ldw" for folder in folders for number in (slot, slot + 20, slot + 40)
            if (folder / f"{base}{number}.ldw").is_file()]


def recognise(save_folder: Path, slot: int, save_name: str,
              pause: Callable[[bytes], bytes | None], folder: Path | None = None) -> bool | None:
    """Link slot ``slot``'s save in ``folder`` (the save folder itself, or one of its backups) to its second
    faction when it has lost it to a pause; the game's copies are looked for in ``save_folder`` and all its
    backups.

    None: nothing to do (no faction file, not a save, or it already has its entry).  True: linked.  False: it
    has no entry and no copy the game wrote pauses to exactly these bytes with an entry of its own."""
    folder = save_folder if folder is None else folder
    target = faction_file(folder, slot)
    if _read(target) is None:
        return None
    try:
        save = (folder / save_name).read_bytes()
    except OSError:
        return None
    fp = fingerprint(save)
    if fp is None or entry_for(target, fp) is not None:
        return None
    suffix = f"{slot}.ldw"
    if not save_name.endswith(suffix):
        return None
    for candidate in _candidates(save_folder, slot, save_name[:-len(suffix)]):
        if candidate == folder / save_name:
            continue
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        cfp = fingerprint(data)
        if cfp is None:
            continue
        source = entry_for(target, cfp) or entry_for(faction_file(candidate.parent, slot), cfp)
        if source is None:
            continue
        try:
            if pause(data) != save:
                continue
        except Exception:  # noqa: BLE001 -- a copy the pause cannot reproduce is simply not this save's
            continue
        return add_entry(target, fp, source)
    return False
