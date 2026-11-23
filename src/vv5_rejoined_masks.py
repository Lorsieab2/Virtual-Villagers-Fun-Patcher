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
Heathen Master (purple mask)" or "Retired Heathen Chief" -- and only when the logs know ONE villager of that
name and sex (Codex, #841): no villager of the name died, vanished or was lost, no island event brought a
newcomer of it, and at most one Birth / Arrived record of their own, which comes before that conversion.
Anything less is listed with why, never guessed.

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


@dataclass
class _Lives:
    """What the logs say of the villagers of one name and sex."""
    events: dict[tuple[str, str], list[tuple[int, str, str | None]]] = field(default_factory=dict)
    # (order, "own", None) a Birth / Arrived record that is not a conversion, (order, "conv", Special villager
    # line) a conversion; order counts every such record of the logs, so two names' records merge in order
    newcomers: set[tuple[str, str]] = field(default_factory=set)   # an island event's newcomer of that name, sex
    gone: set[str] = field(default_factory=set)                    # a villager of that name died, vanished, lost
    renames: list[tuple[str, str]] = field(default_factory=list)   # (old name, new name): every recorded rename
    sex_changed: set[str] = field(default_factory=set)             # names whose sex changed (vv_sex_changes)


def _sex(value: str | None) -> str:
    return (value or "").strip().lower()


def _lives(folder: Path, slot: int) -> _Lives:
    """Every record that tells one villager of a name from another (Codex, #841: a dead convert's record is
    never a living namesake's)."""
    import vv_log_additions as additions
    import vv_original_look as ol
    import vv_log_tools as tools
    import vv_reconcile as rc
    villages = additions.current_villages(folder, GAME, slot)
    files = tools.load_checker().log_files(folder)
    out = _Lives()
    order = 0
    for p in ol._in_order([p for p in files if "Births and Conceptions" in p.name]):
        for b in additions.blocks(p):
            if not b.of(slot, GAME, villages) or b.not_kept:
                continue                                # a record the saved village never held (src/vv_not_kept.py)
            order += 1
            if rc.BIRTH.match(b.heading):
                child = ol._sub_lines(b.lines, "Child")
                if child and child["Name"]:
                    out.events.setdefault((child["Name"], _sex(child.get("Sex"))), []).append((order, "own", None))
            elif b.heading.startswith("Arrived") and b.value("Name"):
                key = (b.value("Name"), _sex(b.value("Sex")))
                if ol._converted(b.value("How")):
                    out.events.setdefault(key, []).append((order, "conv", b.value("Special villager")))
                else:
                    out.events.setdefault(key, []).append((order, "own", None))
    # The names a villager has had (Codex, #841): "Name changed" records, island events' renames and the
    # patcher's own renames -- the same list the original looks follow (src/vv_original_look.py evidence).
    ev = ol.evidence(folder, GAME, slot)
    out.renames = list(ev.renames)
    out.sex_changed = set(ev.sex_changed)
    for p in [p for p in files if "Island Events" in p.name]:
        for b in additions.blocks(p):
            if b.of(slot, GAME, villages) and not b.not_kept and (b.value("New villager") or "").lower().startswith("yes") \
                    and b.value("Name"):
                out.newcomers.add((b.value("Name"), _sex(b.value("Sex"))))
    for p in [p for p in files if "Deaths" in p.name or "Unaccounted" in p.name]:
        for b in additions.blocks(p):
            if b.of(slot, GAME, villages) and not b.not_kept and b.value("Name") \
                    and (b.value("What happened") or "").strip() not in additions.LEFT_RECORDS:
                out.gone.add(b.value("Name"))
    return out


def _rejoined_title(lives: _Lives, name: str, sex: str, others: set[str] = frozenset()) -> tuple[str | None, str]:
    """(the Special villager line of the conversion that is this living villager's, why not) -- under any name
    they have had (a rename since is followed: Codex, #841), and only when the logs know one villager of those
    names and this sex: no other living villager has one of them, no namesake gone for good, no island event's
    newcomer of one, at most one record of their own, and that one before their last conversion.  ("", "")
    when the logs show no conversion of them at all."""
    import vv_original_look as ol
    names = ol._names(name, lives.renames)
    # A sex change since (Codex, #841): their records of the other sex are theirs too -- under a name whose sex
    # changed only, and a second own record of either sex still makes it more than one villager.
    sexes = {sex} | ({"male", "female"} if names & lives.sex_changed else set())
    events = sorted(e for n in names for x in sexes for e in lives.events.get((n, x), []))
    convs = [k for k, e in enumerate(events) if e[1] == "conv"]
    owns = [k for k, e in enumerate(events) if e[1] == "own"]
    if not convs:
        return None, ""
    if names & set(others):
        return None, "another living villager has (or had) one of their names; whose conversion it was cannot be told"
    if names & lives.gone:
        return None, "a villager of their name is gone; whose conversion it was cannot be told"
    if any((n, x) in lives.newcomers for n in names for x in sexes) or len(owns) > 1:
        return None, "the logs know more than one villager of their name"
    if owns and owns[0] > convs[-1]:
        return None, "their own record comes after the conversion: it was another villager's"
    return events[convs[-1]][2] or "", ""


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
    alive, _ = rc.read_save(save, GAME)
    names = [a.name for a in alive]
    lives = _lives(folder, slot)
    import vv_original_look as ol
    for a in alive:
        others: set[str] = set()
        for o in alive:
            if o is not a:
                others |= ol._names(o.name, lives.renames)
        title, why = _rejoined_title(lives, a.name, _sex(str(a.sex or "")), others)
        if title is None and not why:
            continue                                # never rejoined from the Heathens, by the logs
        index = a.record if a.record is not None else -1
        # Every villager the logs show rejoined is either given their mask back or listed with why.
        if a.record is None:
            out.listed.append(Found(a.name, index, None, "their record in the save cannot be told"))
            continue
        if data[a.at + FACTION] != 0:
            out.listed.append(Found(a.name, index, None, "a Heathen now (Restore Heathen Masks is for them)"))
            continue
        if masks is None or masks.weak:
            out.listed.append(Found(a.name, index, None, "there is no Village Masks file the game reads by "
                                                         "identity yet (play the village and save once)"))
            continue
        ident = checker._villager(data, a.at, checker.LAYOUTS[GAME], index, GAME).ident
        if index >= len(masks.values) or masks.stored[index] != ident:
            out.listed.append(Found(a.name, index, None, "the Village Masks file does not name them at their "
                                                         "record yet (play and save once)"))
            continue
        if masks.values[index] != 0:
            worn = masks.values[index]
            out.listed.append(Found(a.name, index, None, f"they wear the "
                                    f"{MASK_NAMES[worn] if worn < len(MASK_NAMES) else f'mask {worn}'} now: "
                                    "left as it is"))
            continue
        if names.count(a.name) != 1:
            out.listed.append(Found(a.name, index, None, "another living villager has their name"))
            continue
        if title is None:
            out.listed.append(Found(a.name, index, None, why))
            continue
        mask = TITLE_MASK.get(title.strip())
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
