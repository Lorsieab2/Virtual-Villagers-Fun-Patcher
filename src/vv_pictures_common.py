"""Picture Studio: what every game's renderer shares (src/vv_pictures_vv1.py ... vv_pictures_vv5.py).

* The save: the villagers the game loads from a slot's save -- the living, the bodies awaiting burial and
  The Lost Children's Esteemed Elder statues -- each with what the save keeps (the log checker's own
  reading, scripts/vvfp_consistency_check.py: vv1_roster / villager_offsets / lookalike / HEALTH), read
  only.
* The patcher's own per-villager files that change a picture, read only, each followed to its villager the
  way the companion that wrote it does on the next load:
    - the Origins cosmetic masks ("Village Masks - Save <S>.dat", every game: the checker's read_mask_file
      and mask_follow, as Check Saves & Logs reads them);
    - Change Appearance's head look ("Head Looks - Save <S>.dat", native/vvfp_head_look: Auto, Young, Old).
  Change Appearance's head, body and mask changes are in the save itself (head, body) and the masks file.
* Ages: 20 age units a year; the old head from 1,100 units (55 years) unless the head look says otherwise.

Nothing here writes anything.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import vv_picture_image as pi

TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
UNITS_PER_YEAR = 20
OLD_AGE = 1100                      # the games' old head: a shown age of 1,100 units (55 years)
ADULT_AGE = 0x118                   # 280 units (14 years): drawn full size from here (every game's draw code)
MASK_NAMES = ("(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask")
LOOK_AUTO, LOOK_YOUNG, LOOK_OLD = 0, 1, 2
LOOK_NAMES = {LOOK_AUTO: "Auto (old from 55)", LOOK_YOUNG: "Young", LOOK_OLD: "Old"}
HEAD_LOOK_MAGIC, HEAD_LOOK_MAGIC_V1 = b"VHL2", b"VHL1"
FNV_BASIS, FNV_PRIME = 2166136261, 16777619


def title(game: int) -> str:
    return f"Virtual Villagers - {TITLES[game]}"


def _checker():
    import vv_log_tools
    return vv_log_tools.load_checker()


def years(age_units: int) -> int:
    return int(age_units) // UNITS_PER_YEAR


def old_head(age_units: int, look: int = LOOK_AUTO) -> bool:
    """Whether the old head is drawn: the head look decides when it is Young or Old, else the age."""
    if look == LOOK_YOUNG:
        return False
    if look == LOOK_OLD:
        return True
    return age_units >= OLD_AGE


# ---------------------------------------------------------------------------------------------- the save

@dataclass
class SaveVillager:
    """One record the game loads from the save (its record number is `rank`)."""
    rank: int
    name: str
    male: bool
    age: int                        # age units
    head: int
    body: int
    health: int                     # 0 or less: a body awaiting burial
    at: int                         # the name's offset in the save file
    data: bytes = field(repr=False, default=b"")
    statue: bool = False            # The Lost Children's Esteemed Elder statue (no villager)
    mask: int = 0                   # the Origins cosmetic mask, 0..5 (MASK_NAMES)
    look: int = LOOK_AUTO           # Change Appearance's head look
    ident: int = 0                  # the mask identity (the checker's mask_identity)

    @property
    def dead(self) -> bool:
        return self.health <= 0

    def i32(self, offset: int) -> int:
        """The dword at `offset` from the name, in the save."""
        return struct.unpack_from("<i", self.data, self.at + offset)[0]

    def u8(self, offset: int) -> int:
        return self.data[self.at + offset]


def save_path(folder: Path, game: int, slot: int) -> Path:
    return Path(folder) / f"{_checker().SAVE_STEMS[game]}{slot}.ldw"


def read_save(folder: Path, game: int, slot: int) -> tuple[bytes, list[SaveVillager]]:
    """(the save's bytes, every record the game loads from it, in record order), read only."""
    checker = _checker()
    data = save_path(folder, game, slot).read_bytes()
    out: list[SaveVillager] = []
    if game == 1:
        first = checker.VV1_BLOCK0 + 0x370 - checker.VV1_BASE
        for v in checker.vv1_roster(data):
            # vv1_roster skips nothing it loads: its rank is the record number
            at = _vv1_name_at(checker, data, v.rank)
            out.append(SaveVillager(v.rank, v.name, v.male, v.age, v.head, v.body, v.health,
                                    at if at is not None else first, data, ident=v.ident))
        return data, out
    lay = checker.LAYOUTS[game]
    for rank, p in enumerate(checker.villager_offsets(game, data, [])):
        ident, _v2, _names = checker.mask_identity(game, data, p, lay)
        out.append(SaveVillager(
            rank=rank, name=checker.cstr(data, p, lay.name_cap),
            male=checker.i32(data, p + lay.gender) == lay.male_value,
            age=checker.i32(data, p + lay.age), head=checker.i32(data, p + lay.head),
            body=checker.i32(data, p + lay.body), health=checker.i32(data, p + checker.HEALTH[game]),
            at=p, data=data, statue=checker.lookalike(data, p, game), ident=ident))
    return data, out


def _vv1_name_at(checker, data: bytes, rank: int) -> int | None:
    """A New Home: the name offset of the rank-th villager vv1_roster lists (it skips nameless records)."""
    n = 0
    for i in range(256):
        base = checker.VV1_BLOCK0 + i * checker.VV1_STRIDE
        if data[base + 0x3D4 - checker.VV1_BASE] != 1:
            return None
        name = checker.cstr(data, base + 0x370 - checker.VV1_BASE, 0x1B)
        gender = checker.i32(data, base + 0x350 - checker.VV1_BASE)
        if not name or gender not in (1, 2):
            continue
        if n == rank:
            return base + 0x370 - checker.VV1_BASE
        n += 1
    return None


def village_name(folder: Path, game: int, slot: int) -> str | None:
    import vv_save_backup
    return vv_save_backup.read_village_name(game, save_path(folder, game, slot))


# ------------------------------------------------------------------------------- the patcher's own files

def _data_file(folder: Path, relative: str) -> Path | None:
    """A patcher data file of the save folder (its newest place), or None when there is none."""
    import vv_save_layout as layout
    checker = _checker()
    rel = f"{checker.DATA}\\{relative}"
    for path in (layout.route(Path(folder), rel), Path(folder) / checker.DATA / Path(relative).name):
        if path.is_file():
            return path
    return None


def masks_by_rank(folder: Path, game: int, slot: int, people: list[SaveVillager]) -> dict[int, int]:
    """Each record's Origins cosmetic mask (1..5), as the companion's next load gives it
    (scripts/vvfp_consistency_check.py read_mask_file + mask_follow; The Secret City by identity)."""
    checker = _checker()
    name = checker.VV_MASK_FILES.get(game, "Village Masks - Save {slot}.dat").format(slot=slot)
    path = _data_file(folder, f"Village Masks\\{name}")
    if path is None:
        return {}
    try:
        masks = checker.read_mask_file(game, path.read_bytes())
    except OSError:
        return {}
    if masks is None:
        return {}
    n = len(masks.values)
    values = [x if x < len(MASK_NAMES) else 0 for x in masks.values]
    if game == 3:
        out = {}
        for v in people:
            found = [k for k in range(n) if values[k] and masks.stored[k] == v.ident]
            if len(found) == 1:
                out[v.rank] = values[found[0]]
        return out
    if masks.legacy:
        return {v.rank: values[v.rank] for v in people if v.rank < n and values[v.rank]}
    # The live roster as the companion sees it after the load: the living villagers' identities by record.
    import vv_log_tools  # noqa: F401  (the checker's own villagers carry the other identities)
    data = people[0].data if people else b""
    roster = _checker_roster(game, data)
    live = [0] * n
    live_v2 = [0] * n
    names = [0] * n
    for r in roster:
        if r.rank < n:
            live[r.rank], live_v2[r.rank], names[r.rank] = r.ident, r.ident_v2, r.name_hash
    against = names if masks.weak else (live_v2 if masks.v2 else live)
    if game in (2, 5) and not checker.roster_same(masks.roster, against):
        return {}
    after, _ids = checker.mask_follow(values, masks.stored, masks.roster, against, masks.weak)
    return {i: after[i] for i in range(n) if after[i]}


def _checker_roster(game: int, data: bytes):
    checker = _checker()
    if game == 1:
        return checker.vv1_roster(data)
    return checker.vv25_roster(game, data, [])


def _fnv_text(h: int, raw: bytes, cap: int) -> int:
    for b in raw[:cap]:
        if b == 0:
            break
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def _fnv_bytes(h: int, raw: bytes) -> int:
    for b in raw:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def head_look_identity(game: int, v: SaveVillager) -> int:
    """native/vvfp_head_look/vvfp_head_look.c hl_identity on the saved entry: FNV-1a of the name (to its
    NUL, at most the name field), 0xFF, then hl_stable (the sex dword and the family (A New Home) or the
    two parents' names with 0xFE / 0xFD); 0 becomes 1."""
    d, at = v.data, v.at
    if game == 1:
        sex, name_bytes = d[at - 0x20:at - 0x1C], 0x1C
        stable = _fnv_bytes(_fnv_bytes(FNV_BASIS, sex), d[at - 4:at])
    else:
        lay = _checker().LAYOUTS[game]
        name_bytes = {2: 0x18}.get(game, 0x19)
        sex = d[at + lay.gender:at + lay.gender + 4]
        stable = _fnv_bytes(FNV_BASIS, sex)
        stable = _fnv_text(stable, d[at + lay.father:at + lay.father + 0x19], 0x19)
        stable = ((stable ^ 0xFE) * FNV_PRIME) & 0xFFFFFFFF
        stable = _fnv_text(stable, d[at + lay.mother:at + lay.mother + 0x19], 0x19)
        stable = ((stable ^ 0xFD) * FNV_PRIME) & 0xFFFFFFFF
    stable = stable or 1
    h = _fnv_text(FNV_BASIS, d[at:at + name_bytes], name_bytes)
    h = ((h ^ 0xFF) * FNV_PRIME) & 0xFFFFFFFF
    h = ((h ^ stable) * FNV_PRIME) & 0xFFFFFFFF
    return h or 1


def head_looks_by_rank(folder: Path, game: int, slot: int, people: list[SaveVillager]) -> dict[int, int]:
    """Each villager's Change Appearance head look (1 Young, 2 Old; Auto is left out), from "Head Looks -
    Save <S>.dat" (native/vvfp_head_look/head_look_store.inc): each look goes to the one villager with
    its stored identity; an identity two villagers share is never guessed at."""
    path = _data_file(folder, f"Head Looks\\Head Looks - Save {slot}.dat")
    if path is None:
        return {}
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    if len(raw) < 12:
        return {}
    magic = raw[:4]
    file_game, count = struct.unpack_from("<II", raw, 4)
    if file_game != game or count not in (150, 256):
        return {}
    if magic == HEAD_LOOK_MAGIC and len(raw) == 12 + count * 9:
        ids = struct.unpack_from(f"<{count}I", raw, 12 + count * 4)
        looks = raw[12 + count * 8:12 + count * 9]
    elif magic == HEAD_LOOK_MAGIC_V1 and len(raw) == 12 + count * 5:
        ids = struct.unpack_from(f"<{count}I", raw, 12)
        looks = raw[12 + count * 4:12 + count * 5]
    else:
        return {}
    idents = {v.rank: head_look_identity(game, v) for v in people}
    shared = {}
    for ident in idents.values():
        shared[ident] = shared.get(ident, 0) + 1
    out = {}
    for k in range(count):
        look = looks[k]
        if look not in (LOOK_YOUNG, LOOK_OLD) or not ids[k]:
            continue
        holders = [rank for rank, ident in idents.items() if ident == ids[k]]
        if len(holders) == 1 and shared[ids[k]] == 1:
            out[holders[0]] = look
    return out


def read_village(folder: Path, game: int, slot: int) -> list[SaveVillager]:
    """Everyone the save holds, with the patcher's masks and head looks on them (read only)."""
    _data, people = read_save(folder, game, slot)
    masks = masks_by_rank(folder, game, slot, people)
    looks = head_looks_by_rank(folder, game, slot, people)
    for v in people:
        v.mask = masks.get(v.rank, 0)
        v.look = looks.get(v.rank, LOOK_AUTO)
    return people


# ---------------------------------------------------------------------------------------------- folders

def save_folders(game: int, documents: Path | None = None) -> list[Path]:
    """Documents\\LDW\\<title>... folders that hold a save of this game: the patched games' first."""
    import vv_save_backup
    documents = documents if documents is not None else vv_save_backup.documents_folder()
    if documents is None:
        return []
    ldw = Path(documents) / "LDW"
    try:
        entries = [e for e in ldw.iterdir() if e.is_dir() and e.name.casefold().startswith(title(game).casefold())]
    except OSError:
        return []
    modded = vv_save_backup.find_save_folders(title(game), documents)
    rest = sorted((e for e in entries if e not in modded), key=lambda p: p.name.casefold())
    return [f for f in modded + rest if any(f.glob("*.ldw"))]


def slots(folder: Path, game: int) -> list[tuple[int, str]]:
    """(slot, village name) of every slot whose save is in `folder`."""
    import vv_save_backup
    return list(vv_save_backup.slot_villages(game, Path(folder)).items())


def age_label(age_units: int) -> str:
    y = years(age_units)
    return f"{y} year{'s' if y != 1 else ''}"


def option_years(first: int, last: int, prefix: str) -> list[pi.Option]:
    """Options "<prefix>, n years" for whole years first..last, keyed by age units."""
    return [pi.Option(y * UNITS_PER_YEAR, f"{prefix}, {y} year{'s' if y != 1 else ''}") for y in range(first, last + 1)]
