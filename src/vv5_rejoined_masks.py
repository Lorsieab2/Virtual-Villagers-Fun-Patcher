"""Repair Saves & Logs: the mask a New Believers villager wore when they rejoined the tribe, given back.

The owner (2026-11-22): villagers who rejoined as "Former Heathen (<colour> mask)" but have no mask now -- Caia and
Nobu, blue -- should have the mask they wore when they rejoined, since Heathens Keep Their Masks When Converted
(native/vvfp_heathens_keep_masks) should have kept it.  Only when the logs prove that mask.

WHAT HAPPENED to them (the owner's 2026-11-22 saves, read only): Keep Masks put the blue mask in their Change
Appearance mask the moment they rejoined; "Reset to original" pressed on them afterwards took it off again, because
their original -- kept while they were believer founders -- has no mask (native/vvfp_original_look
original_look_store.inc ol_converted: a believer who left and came back keeps their own original).  So the
mask is given back here, in the store Keep Masks writes it to: the Origins companion's "Village Masks - Save
<S>.dat" (one nibble per record, kept by the villager's identity; the same file and the same in-place write as
src/vv5_heathen_masks_restore.py on its branch, there for Heathens, here for believers).  The save is never
written.

WHO.  A living believer now (the save's faction byte 0) of one identity, whose name no other living villager
has, whose nibble in the Village Masks file is 0 (no mask) while the file names them at their record, and
whose LAST conversion record in the logs -- an Arrived record "How: Converted from the Heathens" of their name
and sex -- names the mask they wore: "Special villager: Former Heathen (blue / orange / red mask)", "Former
Heathen Master (purple mask)" or "Retired Heathen Chief".  Anything less is listed with why, never guessed.

Run by approve_repair (src/vv_log_tools.py) after the original looks, with the game closed and the save folder
already backed up: the file is copied into "Copies Made Before Repairs" first, written through a temporary
file, and one "Repair <n>" record lists who got which mask."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

GAME = 5
COPY_SUFFIX = ".before-rejoined-masks"
FACTION = -0x1F                     # the save's villager entry, from the name (src/vv5_heathen_masks_restore.py)
MASK_NAMES = ("none", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask")
TITLE_MASK = {"Former Heathen (blue mask)": 1, "Former Heathen (orange mask)": 2, "Former Heathen (red mask)": 3,
              "Former Heathen Master (purple mask)": 4, "Retired Heathen Chief": 5}


@dataclass
class Found:
    name: str
    index: int                      # their record
    mask: int | None                # 1..5 to give back; None: not proven
    why: str = ""

    def line(self) -> str:
        if self.mask is None:
            return f"{self.name}: not given back ({self.why})"
        return f"{self.name}: {MASK_NAMES[self.mask]} (the mask they wore when they rejoined the tribe)"


@dataclass
class Survey:
    path: Path | None
    original: bytes | None
    restore: list[Found] = field(default_factory=list)
    listed: list[Found] = field(default_factory=list)


def _conversions(folder: Path, slot: int) -> dict[tuple[str, str], list[str | None]]:
    """(name, sex) -> the "Special villager" line of each of their conversion records, oldest first."""
    import vv_log_additions as additions
    import vv_original_look as ol
    import vv_log_tools as tools
    villages = additions.current_villages(folder, GAME, slot)
    files = [p for p in tools.load_checker().log_files(folder) if "Births and Conceptions" in p.name]
    out: dict[tuple[str, str], list[str | None]] = {}
    for p in ol._in_order(files):
        for b in additions.blocks(p):
            if not b.of(slot, GAME, villages) or not b.heading.startswith("Arrived"):
                continue
            if not ol._converted(b.value("How")) or not b.value("Name"):
                continue
            out.setdefault((b.value("Name"), (b.value("Sex") or "").strip().lower()), []).append(
                b.value("Special villager"))
    return out


def survey(folder: Path, slot: int) -> Survey:
    """Who gets their mask back, and who cannot (and why).  Reads only."""
    import vv_last_names as ln
    import vv_log_tools as tools
    import vv_reconcile as rc
    folder = Path(folder)
    checker = tools.load_checker()
    save = ln.save_path(folder, GAME, slot)
    data = save.read_bytes()
    path = _masks_path(folder, slot)
    original = path.read_bytes() if path.is_file() else None
    out = Survey(path if original is not None else None, original)
    masks = checker.read_mask_file(GAME, original) if original is not None else None
    if masks is None or masks.weak:
        return out
    alive, _ = rc.read_save(save, GAME)
    names = [a.name for a in alive]
    conversions = _conversions(folder, slot)
    for a in alive:
        titles = conversions.get((a.name, str(a.sex or "").strip().lower()))
        if not titles or a.record is None:
            continue
        at = a.at
        if data[at + FACTION] != 0:
            continue                                # a Heathen now: src/vv5_heathen_masks_restore.py's
        index = a.record
        ident = checker._villager(data, at, checker.LAYOUTS[GAME], index, GAME).ident
        if index >= len(masks.values) or masks.stored[index] != ident:
            out.listed.append(Found(a.name, index, None, "the Village Masks file does not name them at their "
                                                         "record yet (play and save once)"))
            continue
        if masks.values[index] != 0:
            continue                                # wearing a mask: theirs
        if names.count(a.name) != 1:
            out.listed.append(Found(a.name, index, None, "another living villager has their name"))
            continue
        mask = TITLE_MASK.get((titles[-1] or "").strip())
        if mask is None:
            out.listed.append(Found(a.name, index, None, "their last conversion record does not name a mask"))
            continue
        out.restore.append(Found(a.name, index, mask))
    return out


def _masks_path(folder: Path, slot: int) -> Path:
    import vv_save_layout as layout
    name = f"Village Masks - Save {slot}.dat"
    for p in (layout.route(Path(folder), f"{layout.DATA}\\Village Masks\\{name}"), Path(folder) / layout.DATA / name):
        if p.is_file():
            return p
    return layout.route(Path(folder), f"{layout.DATA}\\Village Masks\\{name}")


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
    restored: list[Found] = field(default_factory=list)
    listed: list[Found] = field(default_factory=list)
    note: str = ""


def restore(folder: Path, slot: int, backup_name: str | None = None, now: datetime | None = None) -> Result:
    """Give back every proven mask (approve_repair: the game closed, the save folder backed up)."""
    import vv_last_names as ln
    import vv_log_tools as tools
    folder = Path(folder)
    try:
        work = survey(folder, slot)
    except (struct.error, ValueError, OSError, ln.LastNamesError) as exc:
        return Result(note=f"the rejoined villagers' masks were not checked ({exc})")
    if not work.restore:
        return Result([], work.listed)
    path, original = work.path, work.original
    target = tools.copy_before_repair(folder, path, COPY_SUFFIX)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as copy:
        copy.write(original)
    if path.read_bytes() != original:
        return Result([], work.listed, f"{path.name} changed while it was read; nothing was changed")
    ln._write(path, updated(original, work.restore))
    try:
        _note(folder, slot, work.restore, path, target.name, backup_name, now)
    except OSError:
        pass                                        # the masks stand; Check Saves & Logs still sees them
    return Result(work.restore, work.listed)


def _note(folder: Path, slot: int, restored: list[Found], path: Path, copy: str, backup_name: str | None,
          now: datetime | None) -> None:
    """One "Repair <n>" record in the Repairs Made log."""
    import vv_log_additions as additions
    import vv_log_tools as tools
    import vv_save_layout as layout
    from vv_game_text import GAME_TEXT
    villages = additions.current_villages(folder, GAME, slot) or set()
    header = sorted(villages)[0] if villages else "Village: (all villages in this save folder)"
    log, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(header) or slot, now)
    text += ("  Checked: villagers who rejoined the tribe from the Heathens and have no mask now, against their "
             "conversion records' Former Heathen titles\r\n")
    for f in restored:
        text += f"  Restored: {f.line()}\r\n"
    text += f"  File: {Path(path).relative_to(folder)} -- copy kept: {copy}\r\n"
    if backup_name:
        text += f"  Backup: {backup_name}\r\n"
    text += "\r\n"
    with open(log, "ab") as handle:
        handle.write(text.encode(GAME_TEXT, "replace"))
