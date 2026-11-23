"""Repair Saves & Logs: "Restore Heathen Masks..." (New Believers).

The owner (2026-11-22): "I would like an option in repair logs to restore the proper masks to heathens that
reconverted into heathens."  And the rule for the game (Heathens Keep Their Masks When Converted,
native/vvfp_heathens_keep_masks): "a villager who goes back to the Heathens gets back exactly the mask they wore as
a Heathen before -- blue, orange, red, purple, or the Chief's mask -- whatever it was; behaviour is always an
ordinary blue Heathen."

Villagers who went back before that existed show the blue mask (the Faith drift's "New Heathens Get a Heathen's
Faith" clears the kind bytes; a former Master or Chief has no purple or Chief's mask as an ordinary Heathen).  The
companion draws a Heathen's own mask from the Origins companion's Village Masks file ("Village Masks - Save
<S>.dat": one nibble per record, 1 Blue .. 5 the Tribal Chief's, kept by the villager's identity): for a Heathen
whose role is not a puzzle role (12-17) and whose kind bytes are both 0 -- an ordinary blue Heathen to the game --
a nibble of 2..5 is the mask drawn.  So this tool writes only that file, a patcher file, never the save: the
behaviour stays the blue Heathen's.

WHO.  A Heathen now (the save's faction byte, entry name - 0x1F), of no puzzle role (role, name - 0x14, not
12..17), with neither kind byte (name - 0x1E, name - 0x1D), whom the patcher's data or logs show were a believer
once:
  * the Former Heathens file (native/shared/former_heathens.h, "Former Heathens - Save <S>.dat") has an entry for
    their identity (name, likes, dislikes: VVFP Cause of Death.dll files it at their conversion) -- the mask they
    wore then, certain;
  * else the logs' Village Population and Village History records show them as "Former Heathen (<colour> mask)",
    "Former Heathen Master (purple mask)" or "Retired Heathen Chief" (their name, head and body), every such record
    agreeing -- certain;
  * else the logs show they converted and left again (Arrived "Converted from the Heathens" and Disappeared "Left
    the tribe: became a Heathen"), but nothing says which mask: listed as "mask unknown" and skipped, never guessed.
A mask of blue needs nothing (the game draws the one blue).  The Heathen Mommy, Doctor, Chief and Masters while
they are those Heathens are never touched (their role draws their mask).

WHAT IS WRITTEN.  Their nibble in the slot's Village Masks file, when the file is one the game reads (VM06 or
VM26: identities) and names them at their record -- the companion's own rule: an entry is theirs only when the
file's roster holds their identity there.  A file that does not name them yet (made before they were saved) is
not written for them; they are listed with why.

survey() reads only.  restore() refuses while the game runs, backs the save folder up first (Back Up Saves'
copier, BACKUP_LABEL), copies the file into "Copies Made Before Repairs", writes it through a temporary file and
reads it back (put back on a failure), and writes one "Repair <n>" record in the Repairs Made log."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout
from vv_game_text import GAME_TEXT  # the games' bytes: Windows-1252, every byte kept

GAME = 5
BACKUP_LABEL = "(before restoring Heathen masks)"
COPY_SUFFIX = ".before-heathen-masks"

# The save's villager entry, from the name (the writer 0x4652F0: entry +0 present, +1 faction, +2 orange,
# +3 red, +0xC role; the name at entry +0x20).
FACTION, ORANGE, RED, ROLE = -0x1F, -0x1E, -0x1D, -0x14
PUZZLE_ROLES = range(12, 18)                 # the Heathen Doctor, Chief, three Masters, Mommy

FORMER_FILE = layout.DATA + "\\Former Heathens\\Former Heathens - Save {slot}.dat"
FORMER_MAGIC, FORMER_VERSION, FORMER_HEADER, FORMER_ENTRY = b"VFH1", 1, 16, 8

MASK_NAMES = ("none", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask")
# Former Heathens kinds (VV_FORMER_*) -> the Village Masks value.
KIND_MASK = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
# The logs' Special villager titles of a former Heathen (native/shared/former_heathens.h vv_former_title).
TITLE_MASK = {"Former Heathen (blue mask)": 1, "Former Heathen (orange mask)": 2, "Former Heathen (red mask)": 3,
              "Former Heathen Master (purple mask)": 4, "Retired Heathen Chief": 5}


class HeathenMasksError(Exception):
    """Nothing was changed (or everything was put back); the message says why."""


@dataclass
class Found:
    name: str
    head: int
    body: int
    index: int                      # their record number
    mask: int | None                # 2..5 to give back; None: not known
    source: str                     # where the mask is known from (or why not)
    note: str | None = None         # set: listed, not written (why)

    def line(self) -> str:
        who = f"{self.name} (head {self.head}, body {self.body})"
        if self.mask is None:
            return f"{who}: mask unknown -- skipped ({self.source})"
        what = f"{who}: {MASK_NAMES[self.mask]} (from {self.source})"
        return what + (f" -- not restored: {self.note}" if self.note else "")


@dataclass
class Survey:
    path: Path | None               # the Village Masks file
    original: bytes | None
    restore: list[Found] = field(default_factory=list)     # certain and writable
    listed: list[Found] = field(default_factory=list)      # unknown, or not writable
    notes: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [f.line() for f in self.restore] + [f.line() for f in self.listed] + self.notes


def masks_path(folder: Path, slot: int) -> Path:
    """The slot's Village Masks file where the companion reads it (scripts/vvfp_consistency_check.py
    check_masks): the save's own Data folder, or the older layout's."""
    name = f"Village Masks - Save {slot}.dat"
    for p in (layout.route(Path(folder), f"{layout.DATA}\\Village Masks\\{name}"), Path(folder) / layout.DATA / name):
        if p.is_file():
            return p
    return layout.route(Path(folder), f"{layout.DATA}\\Village Masks\\{name}")


def _former(folder: Path, slot: int) -> dict[int, list[int]] | None:
    path = layout.route(Path(folder), FORMER_FILE.format(slot=slot))
    if not path.is_file():
        return {}
    data = path.read_bytes()
    if len(data) < FORMER_HEADER or data[:4] != FORMER_MAGIC \
            or struct.unpack_from("<II", data, 4) != (FORMER_VERSION, GAME):
        return None
    count = struct.unpack_from("<I", data, 12)[0]
    if len(data) != FORMER_HEADER + count * FORMER_ENTRY:
        return None
    out: dict[int, list[int]] = {}
    for k in range(count):
        identity, kind = struct.unpack_from("<II", data, FORMER_HEADER + k * FORMER_ENTRY)
        out.setdefault(identity, []).append(kind)
    return out


def _log_evidence(folder: Path, slot: int) -> tuple[dict[tuple, set[int]], set[tuple]]:
    """(name, head, body) -> the masks every former-Heathen title of theirs in the slot's logs names; and who the
    logs show converted from the Heathens and left for them again."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    titles: dict[tuple, set[int]] = {}
    villages = additions.current_villages(folder, GAME, slot)
    for path in checker.log_files(folder):
        try:
            found = additions.blocks(path)
        except (OSError, UnicodeDecodeError):
            continue
        for b in found:
            if not b.of(slot, GAME, villages) or not b.heading.startswith("Villager "):
                continue
            mask = TITLE_MASK.get(b.value("Special villager") or "")
            if mask is not None and None not in b.identity:
                titles.setdefault(b.identity, set()).add(mask)
    converted, left, _believer = additions._faction_events(folder, GAME, slot)
    return titles, converted & left


def survey(folder: Path, slot: int) -> Survey:
    """Who can have their mask given back, and who cannot (and why).  Reads only."""
    folder = Path(folder)
    checker = tools.load_checker()
    data = ln.save_path(folder, GAME, slot).read_bytes()
    offsets = checker.villager_offsets(GAME, data, [])
    f = ln.FIELDS[GAME]
    path = masks_path(folder, slot)
    original = path.read_bytes() if path.is_file() else None
    out = Survey(path if original is not None else None, original)
    former = _former(folder, slot)
    if former is None:
        out.notes.append("The Former Heathens file is not one this game reads, so it is not used.")
        former = {}
    titles, went_back = _log_evidence(folder, slot)
    masks = checker.read_mask_file(GAME, original) if original is not None else None
    for index, at in enumerate(offsets):
        if data[at + FACTION] == 0 or data[at + ORANGE] or data[at + RED]:
            continue                                # a believer, or a Heathen whose kind bytes draw their mask
        role = struct.unpack_from("<i", data, at + ROLE)[0]
        if role in PUZZLE_ROLES or struct.unpack_from("<i", data, at + checker.HEALTH[GAME])[0] <= 0:
            continue                                # a puzzle Heathen (their role draws it), or a body
        who = (ln._cstr(data, at, f.name_cap), struct.unpack_from("<i", data, at + f.head)[0],
               struct.unpack_from("<i", data, at + f.body)[0])
        kinds = former.get(ln._title_identity(data, at, f), [])
        mask, source = None, ""
        if len(kinds) == 1 and kinds[0] in KIND_MASK:
            mask, source = KIND_MASK[kinds[0]], "the Former Heathens file"
        elif len(kinds) > 1:
            source = "two Former Heathens entries share their identity"
        elif len(titles.get(who, ())) == 1:
            mask, source = next(iter(titles[who])), "their Former Heathen title in the logs"
        elif len(titles.get(who, ())) > 1:
            source = "their Former Heathen titles in the logs disagree"
        elif who in went_back:
            source = "the logs show they joined the tribe and went back, but not which mask they wore"
        else:
            continue                                # never shown to be a believer: an ordinary Heathen
        found = Found(*who, index, mask, source)
        if mask is None:
            out.listed.append(found)
            continue
        if mask == 1:
            continue                                # blue: the game's own blue is theirs
        ident = checker._villager(data, at, checker.LAYOUTS[GAME], index, GAME).ident
        if masks is None:
            found.note = ("there is no Village Masks file the game reads yet (play the village with Heathens Keep "
                          "Their Masks When Converted and save once)")
        elif masks.weak or index >= len(masks.values) or masks.stored[index] != ident:
            found.note = "the Village Masks file does not name them at their record yet (play and save once)"
        elif masks.values[index] == mask:
            continue                                # already theirs
        if found.note:
            out.listed.append(found)
        else:
            out.restore.append(found)
    return out


def updated(original: bytes, restore: list[Found]) -> bytes:
    """The Village Masks file with each villager's nibble set, every other byte as it was (VM06 / VM26)."""
    count = 150 if original[:4] in (b"VM05", b"VM06") else 256
    out = bytearray(original)
    base = 4 + count * 4
    for f in restore:
        at = base + (f.index >> 1)
        out[at] = ((out[at] & 0x0F) | (f.mask << 4)) if f.index & 1 else ((out[at] & 0xF0) | f.mask)
    return bytes(out)


@dataclass
class Result:
    restored: list[Found]
    copy: str
    backup: object


def restore(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
            now: datetime | None = None) -> Result:
    """Give back every certain mask.  The survey is made again here, so nothing is written from a stale one.
    Refused while the game runs; the save folder is backed up first; a failure puts the file back."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    try:
        work = survey(folder, slot)
    except (struct.error, ValueError, OSError, ln.LastNamesError) as exc:
        raise HeathenMasksError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.restore:
        raise HeathenMasksError("No Heathen's mask was found to restore.")
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise HeathenMasksError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    path, original = work.path, work.original
    for k in range(1, 1000):
        target = tools.copy_before_repair(folder, path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not target.exists():
            break
    else:
        raise HeathenMasksError(f"{path.name} has too many copies already; nothing was changed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as copy:
        copy.write(original)
    try:
        if path.read_bytes() != original:
            raise HeathenMasksError(f"{path.name} changed while it was being read; nothing was changed.")
        ln._write(path, updated(original, work.restore))
    except (OSError, ln.LastNamesError) as exc:
        try:
            if path.read_bytes() != original:
                ln._write(path, original)
        except (OSError, ln.LastNamesError):
            raise HeathenMasksError(f"Restoring the masks failed ({exc}) and {path.name} could not be put back. "
                                    f"Your backup is in {backup.backup_folder}.") from exc
        raise HeathenMasksError(f"Restoring the masks failed ({exc}); {path.name} was put back as it was. "
                                f"A backup is in {backup.backup_folder}.") from exc
    try:
        _note(folder, slot, work.restore, path, target.name, backup, now)
    except OSError:
        pass                                # the restore stands; Check Saves & Logs still sees it
    return Result(work.restore, target.name, backup)


def _village(folder: Path, slot: int) -> str | None:
    import vv_log_additions as additions
    names = additions.current_villages(folder, GAME, slot) or set()
    return sorted(names)[0] if names else None


def _note(folder: Path, slot: int, restored: list[Found], path: Path, copy: str, backup, now) -> None:
    """One "Repair <n>" record in the Repairs Made log (src/vv_lost_titles.py note_restore's shape)."""
    header = _village(folder, slot) or "Village: (all villages in this save folder)"
    log, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(header) or slot, now)
    text += ("  Checked: Heathens who joined the tribe and went back to the Heathens, against the Former Heathens "
             "file and the logs' Former Heathen titles\r\n")
    for f in restored:
        text += f"  Restored: {f.name} (head {f.head}, body {f.body}): {MASK_NAMES[f.mask]} (from {f.source})\r\n"
    text += f"  File: {Path(path).relative_to(folder)} -- copy kept: {copy}\r\n"
    text += f"  Backup: {Path(backup.backup_folder).name}\r\n\r\n"
    with open(log, "ab") as handle:
        handle.write(text.encode(GAME_TEXT, "replace"))
