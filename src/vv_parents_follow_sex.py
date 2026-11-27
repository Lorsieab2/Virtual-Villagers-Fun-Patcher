"""Repair Saves & Logs: the parents follow their sex (the owner, 2026-11-27, all five games).

Villagers of any sex may carry a baby (the owner, 2026-11-25), and every game copies the villager who CARRIED into
the newborn's Mother fields and the carrier's expected other parent into its Father fields.  So a man who carried a
woman's baby was recorded as the child's Mother and the woman as its Father -- New Believers' Heathen Mommy Ahi
Mashudu and Vaihi Salongo's daughter Coral Siutiti listed Mother "Ahi Mashudu", Father "Vaihi Salongo" -- and the
Details screen drew each with the other sex's head and body sheets.  The owner: "make sure the parents appearances
and names are fixed".

THE RULE.  When the two parents' sexes differ, the woman is the Mother and the man the Father, whoever carried; each
keeps their own name, head and body.  Two of one sex keep the carrier as the Mother.  The companions give every new
birth its parents so (native/parentage_export parents_follow_sex, native/vvfp_heathen_aging follow_sex,
native/vv1_parentage vv1_follow_sex); this puts right the children recorded before.

WHAT IS DECIDED, per recorded pair of parents (a Mother and a Father, each a name, head and body):
  * the Mother recorded as a man and the Father as a woman -- by every sex the save and the logs record for that
    villager (the save's living and unburied, every record's "Sex:" line: snapshots, Deaths, Arrived, a Birth's
    Child, a Conception's Mother and Father) -- swap;
  * the Mother a woman, or the Father a man (each the one sex recorded): nothing is wrong (or the parents are of one
    sex, and the carrier stays the Mother): left alone;
  * otherwise, when one of them points that way (the Mother recorded a man, or the Father a woman) and the other's
    sex is not recorded or both sexes are (a change of sex): the player is asked; "Don't know" changes nothing.
  Nothing is guessed, and a pair with a placeholder parent ("Unknown", "?", "Joey", "(unknown)") is never touched.

WHERE.  The logs (a copy of each first, through src/vv_log_additions.py apply): every Birth record of the pair gets the
two parents' lines traded and "Note: Carried by <him>, who is male (named as the Father; <her> is named as the
Mother)" -- the words the companions write, which the readers that pair a pregnancy with its Birth follow
(vv_log_additions.birth_carrier); every History / Population snapshot's and Unaccounted record's "Parents:" section
of the pair is traded too.  Conception records are left as they are: they record who carried.  Then the save and the
patcher's files (write_save, after the logs, as the graves are): The Lost Children to New Believers' child records
(their parents' fields), the Head Looks, Gender Presentation and New Believers' Masks Worn files and the Village
Masks file re-keyed (their identities include the parents' names), the Unaccounted roster's copies, and A New Home's
Parentage Records (the parents it keeps for each villager).  Repair Saves & Logs backed the save folder up first;
each file is copied into Copies Made Before Repairs as well, and put back on a failure.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_additions as additions
import vv_log_tools as tools

KIND_ID = "parents_sex"
LABEL = ("Parents by their sex (a child recorded with a man as its Mother and a woman as its Father, whoever "
         "carried, gets her as the Mother and him as the Father)")
CHECKED = ("the parents of every child in the save and the Birth, History, Population and Unaccounted records, "
           "against the sex the save and the logs record for each parent, and the player's answers")
ADDED = "Parents put by their sex"
NO = "No: leave them as recorded"
COPY_SUFFIX = ".before-parents-by-sex"
NOTE = "  Note: Carried by {carrier}, who is male (named as the Father; {mother} is named as the Mother)"
PLACEHOLDERS = {"unknown", "?", "joey", "none", "unnamed"}

Identity = tuple  # (name, head, body)


def _real(who: Identity | None) -> bool:
    return (who is not None and len(who) == 3 and bool(who[0]) and None not in who
            and who[0].strip("() ").lower() not in PLACEHOLDERS and not who[0].startswith("("))


def _yes(mother: Identity, father: Identity) -> str:
    return f"Yes: {father[0]} is the Mother and {mother[0]} the Father"


@dataclass
class Pair:
    mother: Identity
    father: Identity
    children: set = field(default_factory=set)       # the children's names, for the question
    decided: bool = False                             # swapped without asking
    question: str | None = None                       # ...or on this question's "Yes"


# ---------------------------------------------------------------------------
# The sexes recorded
# ---------------------------------------------------------------------------

def sexes(folder: Path, game: int, slot: int) -> dict[Identity, set[str]]:
    """Every sex recorded for each (name, head, body): the save's villagers (living and unburied) and every "Sex:"
    line of this slot's village's records."""
    import vv_last_names as ln
    out: dict[Identity, set[str]] = {}

    def add(who, sex):
        if who is not None and None not in who and who[0] and sex in ("Male", "Female"):
            out.setdefault(tuple(who), set()).add(sex)
    try:
        for v in ln.living(folder, game, slot, bodies=True):
            add(v.identity, v.sex)
    except (OSError, ValueError, KeyError, IndexError, struct.error, ln.LastNamesError):
        pass
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    for path in checker.log_files(Path(folder)):
        try:
            found = additions.blocks(path)
        except OSError:
            continue
        for b in found:
            if not b.of(slot, game, villages):
                continue
            if additions.PERSON_HEAD.match(b.heading):
                add(b.identity, b.value("Sex"))
            elif additions.is_birth(b.heading):
                add(additions._sub_identity(b, "Child"), additions._sub_value(b, "Child", "Sex"))
            elif b.heading.startswith("Conception"):
                for label in ("Mother", "Father"):
                    add(additions._sub_identity(b, label), additions._sub_value(b, label, "Sex"))
            elif b.heading == "Couple formed":
                for label in ("First", "Second"):
                    add(additions._sub_identity(b, label), additions._sub_value(b, label, "Sex"))
    return out


def _one(found: set[str] | None) -> str | None:
    return next(iter(found)) if found and len(found) == 1 else None


# ---------------------------------------------------------------------------
# The parents recorded
# ---------------------------------------------------------------------------

def _save_parents(folder: Path, game: int, slot: int) -> list[tuple[int, Identity, Identity, str]]:
    """The Lost Children to New Believers: (name offset, mother, father, child's name) of every villager the save
    loads (living and unburied)."""
    import vv_last_names as ln
    if game == 1:
        return []
    f = ln.FIELDS[game]
    try:
        data = ln.save_path(folder, game, slot).read_bytes()
        people = ln.living(folder, game, slot, bodies=True)
    except (OSError, ValueError, KeyError, IndexError, struct.error, ln.LastNamesError):
        return []
    fh, fb, mh, mb, _eh, _eb = f.looks
    out = []
    for v in people:
        mother = (ln._cstr(data, v.at + f.mother, f.parent_cap), ln._i32(data, v.at + mh), ln._i32(data, v.at + mb))
        father = (ln._cstr(data, v.at + f.father, f.parent_cap), ln._i32(data, v.at + fh), ln._i32(data, v.at + fb))
        out.append((v.at, mother, father, v.name))
    return out


def _vv1_files(folder: Path, slot: int) -> list[Path]:
    import vv_save_layout as layout
    data_dir = Path(folder) / tools.DATA
    return [layout.route(Path(folder), f"{layout.DATA}\\{layout.PARENTS_VV1}\\"
                                       f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"),
            data_dir / f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"]


VV1_ENTRIES = 12 + 256 * 36                  # the 92-byte entries after the 256 occupants


def _vv1_entries(raw: bytes) -> list[tuple[int, str]]:
    """(entry offset, the villager's name) of every entry of A New Home's Parentage Records: the 256 by record, and
    the departed list after them (src/vv1_parents_restore.py)."""
    import vv_last_names as ln
    out = []
    if raw[:4] != b"VP02" or len(raw) < VV1_ENTRIES + 256 * 92:
        return out
    for i in range(256):
        occ = 12 + i * 36
        if raw[occ] in (1, 2):
            out.append((VV1_ENTRIES + i * 92, ln._cstr(raw, occ + 8, 28)))
    if len(raw) > VV1_ENTRIES + 256 * 92:
        import vv1_parents_restore as parents_file
        listed = parents_file.departed_list(bytes(raw))
        for k in range(len(listed or ())):
            at = VV1_ENTRIES + 256 * 92 + 8 + k * 128
            out.append((at + 36, ln._cstr(raw, at + 8, 28)))
    return out


def _vv1_entry_parents(raw: bytes, e: int) -> tuple[Identity | None, Identity | None]:
    import vv_last_names as ln

    def who(looks: int, at: int):
        name = ln._cstr(raw, e + at, 28)
        if not name or not raw[e + looks] or not raw[e + looks + 1]:
            return None
        return (name, raw[e + looks] - 1, raw[e + looks + 1] - 1)
    return who(2, 36), who(0, 8)                 # (mother, father)


def _sections(b) -> list[dict]:
    """Every parent pair a record names: a Birth record's "  Mother:" / "  Father:" (kind "birth"), a snapshot's or
    an Unaccounted record's "  Parents:" section's "    Father:" / "    Mother:" (kind "parents"); each with the line
    index of each label's name, head and body (head and body None when the record gives none)."""
    out = []
    lines = b.lines

    def group(k: int, indent: str) -> dict:
        name = lines[k].split(":", 1)[1].strip()
        found = {"name": (b.start + k, lines[k]), "head": None, "body": None, "value": [name, None, None]}
        for j in range(k + 1, len(lines)):
            line = lines[j]
            if not line.startswith(indent + "  "):
                break
            m = re.match(rf"^{indent}  (Head|Body): (-?\d+)\s*$", line)
            if m:
                slot = "head" if m.group(1) == "Head" else "body"
                found[slot] = (b.start + j, line)
                found["value"][1 if slot == "head" else 2] = int(m.group(2))
        found["value"] = tuple(found["value"])
        return found
    if additions.is_birth(b.heading):
        at = {label: k for k, line in enumerate(lines) for label in ("Mother", "Father")
              if line.startswith(f"  {label}:")}
        if "Mother" in at and "Father" in at:
            out.append({"kind": "birth", "Mother": group(at["Mother"], "  "), "Father": group(at["Father"], "  "),
                        "child": additions._sub_identity(b, "Child")})
        return out
    for k, line in enumerate(lines):
        if line.rstrip() != "  Parents:":
            continue
        at = {}
        for j in range(k + 1, len(lines)):
            if not lines[j].startswith("    "):
                break
            for label in ("Father", "Mother"):
                if lines[j].startswith(f"    {label}:"):
                    at.setdefault(label, j)
        if "Mother" in at and "Father" in at:
            out.append({"kind": "parents", "Mother": group(at["Mother"], "    "),
                        "Father": group(at["Father"], "    "), "child": b.identity})
    return out


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

def plan_kind(folder: Path, game: int, slot: int) -> additions.Kind:
    """The kind (see the module's words).  Reads only."""
    folder = Path(folder)
    kind = additions.Kind(KIND_ID, LABEL)
    kind.context = {"game": game, "slot": slot, "pairs": {}, "records": {}}
    recorded = sexes(folder, game, slot)
    pairs: dict[tuple, Pair] = {}

    def pair_of(mother, father, child) -> Pair | None:
        if not (_real(mother) and _real(father)) or mother == father:
            return None
        p = pairs.setdefault((mother, father), Pair(mother, father))
        if child:
            p.children.add(child)
        return p
    held: list[tuple] = []                             # the pair of each villager the save or the file keeps
    for _at, mother, father, child in _save_parents(folder, game, slot):
        pair_of(mother, father, child)
        held.append((mother, father))
    if game == 1:
        for path in _vv1_files(folder, slot):
            try:
                raw = path.read_bytes() if path.is_file() else b""
            except OSError:
                continue
            for e, child in _vv1_entries(raw):
                mother, father = _vv1_entry_parents(raw, e)
                pair_of(mother, father, child)
                held.append((mother, father))
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    found: list[tuple] = []                            # (block, section)
    for path in checker.log_files(folder):
        try:
            every = additions.blocks(path)
        except OSError:
            continue
        for b in every:
            if not b.of(slot, game, villages) or b.not_kept:
                continue
            for s in _sections(b):
                mother, father = s["Mother"]["value"], s["Father"]["value"]
                if s["kind"] == "birth" or None not in mother + father:
                    pair_of(mother, father, (s["child"] or ("",))[0])
                found.append((b, s))
    # Each pair decided, asked about, or left alone.
    for key, p in sorted(pairs.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        m_sexes, f_sexes = recorded.get(p.mother, set()), recorded.get(p.father, set())
        m_one, f_one = _one(m_sexes), _one(f_sexes)
        if m_one == "Male" and f_one == "Female":
            p.decided = True
        elif m_one == "Female" or f_one == "Male":
            continue                                   # right already, or the parents are of one sex
        elif "Male" in m_sexes or "Female" in f_sexes:
            q = f"parents_sex|{p.mother[0]}|{p.mother[1]}|{p.mother[2]}|{p.father[0]}|{p.father[1]}|{p.father[2]}"
            mother_words = (f"{p.mother[0]} (the Mother) is recorded as a man" if m_one == "Male"
                            else f"{p.mother[0]} (the Mother) is recorded as both a man and a woman" if m_sexes
                            else f"{p.mother[0]}'s sex (the Mother) is not recorded")
            father_words = (f"{p.father[0]} (the Father) as a woman" if f_one == "Female"
                            else f"{p.father[0]} (the Father) as both a man and a woman" if f_sexes
                            else f"{p.father[0]}'s sex (the Father) is not recorded")
            children = ", ".join(sorted(p.children)) or "A child"
            kind.questions[q] = additions.Question(
                q, f"{children}: {mother_words}; {father_words}. The woman should be the Mother and the man the "
                   f"Father, whoever carried. Is {p.father[0]} (head {p.father[1]}, body {p.father[2]}) the woman "
                   f"and {p.mother[0]} (head {p.mother[1]}, body {p.mother[2]}) the man?",
                [_yes(p.mother, p.father), NO, additions.DONT_KNOW], additions.DONT_KNOW,
                f"parents_sex:{p.mother}:{p.father}", (p.mother, p.father))
            p.question = q
        else:
            continue
        kind.context["pairs"][key] = p
    # The records' lines of each pair decided or asked about.
    for b, s in found:
        mother, father = s["Mother"]["value"], s["Father"]["value"]
        p = kind.context["pairs"].get((mother, father))
        if p is None and s["kind"] == "parents" and None in mother + father:
            # A names-only "Parents:" section (an Unaccounted record): the pair whose names these are, when there is
            # exactly one such pair of interest and no other pair of the save or logs has the same two names.
            same = [q for k, q in pairs.items() if (k[0][0], k[1][0]) == (mother[0], father[0])]
            p = same[0] if len(same) == 1 and same[0] in kind.context["pairs"].values() else None
        if p is None:
            continue
        needs = () if p.decided else ((p.question, _yes(p.mother, p.father)),)
        for label, other in (("Mother", "Father"), ("Father", "Mother")):
            mine, theirs = s[label], s[other]
            indent = "  " if s["kind"] == "birth" else "    "
            kind.replaces.append((b.path, mine["name"][0], f"{indent}{label}: {theirs['value'][0]}", *(
                (needs,) if needs else ())))
            for part in ("head", "body"):
                if mine[part] is not None and theirs[part] is not None:
                    word = "Head" if part == "head" else "Body"
                    kind.replaces.append((b.path, mine[part][0], f"{indent}  {word}: {theirs['value'][1 if part == 'head' else 2]}",
                                          *((needs,) if needs else ())))
        if s["kind"] == "birth":
            note = NOTE.format(carrier=p.mother[0], mother=p.father[0])
            end = b.start + len(b.lines) - 1
            if p.decided:
                kind.inserts.append(additions.Insert(b.path, end, 8, line=note))
            else:
                kind.inserts.append(additions.Insert(b.path, end, 8, question=p.question,
                                                     by_answer={_yes(p.mother, p.father): note}))
        records = kind.context["records"].setdefault(str(b.path), [])
        records.append((p.question, _yes(p.mother, p.father)) if not p.decided else None)
    # For the checklist row: the records and villagers the plan would put right (asked ones counted too).
    kind.context["found"] = sum(len(v) for v in kind.context["records"].values()) + sum(
        1 for key in held if key in kind.context["pairs"])
    decided = [p for p in kind.context["pairs"].values() if p.decided]
    if decided:
        kind.notes.append("Recorded with a man as the Mother and a woman as the Father, given her as the Mother and "
                          "him as the Father: " + "; ".join(
                              f"{', '.join(sorted(p.children)) or 'a child'} (Mother {p.father[0]}, Father "
                              f"{p.mother[0]})" for p in decided) + ".")
    return kind


def _wanted(kind: additions.Kind, answers: dict[str, str]) -> list[Pair]:
    return [p for p in kind.context.get("pairs", {}).values()
            if p.decided or (p.question and answers.get(p.question) == _yes(p.mother, p.father))]


def records_swapped(kind: additions.Kind, path: str, answers: dict[str, str]) -> int:
    """How many records of the log at `path` (as planned) the answers swap."""
    return sum(1 for need in kind.context.get("records", {}).get(path, [])
               if need is None or answers.get(need[0]) == need[1])


# ---------------------------------------------------------------------------
# The save and the patcher's files
# ---------------------------------------------------------------------------

def _swap_save(buf: bytearray, at: int, f) -> None:
    span = f.mother - f.father
    fh, fb, mh, mb, _eh, _eb = f.looks
    father = bytes(buf[at + f.father:at + f.father + span])
    buf[at + f.father:at + f.father + span] = buf[at + f.mother:at + f.mother + span]
    buf[at + f.mother:at + f.mother + span] = father
    for a, b in ((fh, mh), (fb, mb)):
        x, y = struct.unpack_from("<i", buf, at + a)[0], struct.unpack_from("<i", buf, at + b)[0]
        struct.pack_into("<i", buf, at + a, y)
        struct.pack_into("<i", buf, at + b, x)


def plan_save(folder: Path, game: int, slot: int, kind: additions.Kind,
              answers: dict[str, str]) -> tuple[list, list[str]]:
    """The save's and the patcher's files' new bytes (vv_last_names Change), and who is swapped.  Reads only."""
    import vv_last_names as ln
    folder = Path(folder)
    wanted = {(p.mother, p.father) for p in _wanted(kind, answers)}
    changes: list = []
    who: list[str] = []
    if not wanted:
        return changes, who
    result = ln.Plan({})
    data_dir = folder / tools.DATA
    if game == 1:
        for path in _vv1_files(folder, slot):
            if not path.is_file():
                continue
            original = path.read_bytes()
            buf = bytearray(original)
            for e, child in _vv1_entries(original):
                mother, father = _vv1_entry_parents(original, e)
                if (mother, father) in wanted:
                    # father looks (0, 1) and name (8); mother looks (2, 3) and name (36)
                    buf[e:e + 2], buf[e + 2:e + 4] = original[e + 2:e + 4], original[e:e + 2]
                    buf[e + 8:e + 36], buf[e + 36:e + 64] = original[e + 36:e + 64], original[e + 8:e + 36]
                    who.append(child)
            if bytes(buf) != original:
                changes.append(ln.Change(path, original, bytes(buf), "A New Home's parents"))
    else:
        f = ln.FIELDS[game]
        path = ln.save_path(folder, game, slot)
        original = path.read_bytes()
        buf = bytearray(original)
        worn_map: dict[int, int] = {}
        mask_map: dict[int, int] = {}
        for at, mother, father, child in _save_parents(folder, game, slot):
            if (mother, father) not in wanted:
                continue
            old_worn, old_masks = ln._store_identity(game, buf, at, f), ln._mask_identities(game, buf, at)
            _swap_save(buf, at, f)
            new_worn, new_masks = ln._store_identity(game, buf, at, f), ln._mask_identities(game, buf, at)
            if old_worn != new_worn:
                worn_map[old_worn] = new_worn
            for old_id, new_id in zip(old_masks, new_masks):
                if old_id and new_id and old_id != new_id:
                    mask_map[old_id] = new_id
            who.append(child)
        if bytes(buf) == original:
            return changes, who
        result.changes.append(ln.Change(path, original, bytes(buf), "the save"))
        ln._plan_masks(result, game, slot, data_dir, mask_map, {})
        for subfolder, name, magics, what in (
                ("Head Looks", f"Head Looks - Save {slot}.dat", (b"VHL2", b"VHL1"), "the head looks"),
                ("Gender Presentation", f"Gender Presentation - Save {slot}.dat", (b"VGP1",),
                 "the gender presentations"),
                *((("Heathens Keep Masks", f"Masks Worn - Save {slot}.dat", (b"VKM1",), "the masks worn"),)
                  if game == 5 else ())):
            ln._plan_look_store(result, ln._data_file(folder, subfolder, name), magics, game, worn_map, {}, what)
        changes += result.changes
    changes += _plan_roster(folder, game, slot, wanted)
    return changes, who


def _plan_roster(folder: Path, game: int, slot: int, wanted: set) -> list:
    """The Unaccounted roster's copies of the villagers (native/vvfp_cause_of_death cod_roster.inc): their parents
    as the save now has them (A New Home's version 3: the parents' names after each entry)."""
    import vv_last_names as ln
    import vv_save_layout as layout
    out = []
    data_dir = Path(folder) / tools.DATA
    name = f"Virtual Villagers {game} Villagers at Last Save - Save {slot}.dat"
    names_only = {(m[0], f[0]) for m, f in wanted}
    rec = ln.RECORD[game]
    for path in (layout.route(Path(folder), f"{layout.DATA}\\Unaccounted Villagers\\{name}"),
                 data_dir / f"Virtual Villagers {game} Village Roster - Save {slot}.dat"):
        if not path.is_file():
            continue
        original = path.read_bytes()
        if original[:4] != b"VCR1" or len(original) < 32:
            continue
        version = struct.unpack_from("<I", original, 4)[0]
        count, lo, hi = struct.unpack_from("<III", original, 12)
        tail = 64 if version == 3 and game == 1 else 0
        if not lo <= rec["name"] < hi or len(original) != 32 + count * (16 + hi - lo + tail):
            continue
        size = 16 + (hi - lo) + tail
        buf = bytearray(original)
        for i in range(count):
            entry = 32 + i * size
            base = entry + 16 - lo
            if tail:
                fa, mo = entry + size - 64, entry + size - 32
                if (ln._cstr(original, mo, 32), ln._cstr(original, fa, 32)) in names_only:
                    buf[fa:fa + 32], buf[mo:mo + 32] = original[mo:mo + 32], original[fa:fa + 32]
                continue
            if "father" not in rec:
                continue
            (fn, fh, fb), (mn, mh, mb) = rec["father"], rec["mother"]
            if not all(lo <= off and off + 4 <= hi for off in (fh, fb, mh, mb)) or not (lo <= fn and mn + 0x19 <= hi):
                continue
            cap = ln.FIELDS[game].parent_cap
            mother = (ln._cstr(original, base + mn, cap), ln._i32(original, base + mh), ln._i32(original, base + mb))
            father = (ln._cstr(original, base + fn, cap), ln._i32(original, base + fh), ln._i32(original, base + fb))
            if (mother, father) not in wanted:
                continue
            span = mn - fn
            buf[base + fn:base + fn + span], buf[base + mn:base + mn + span] = \
                original[base + mn:base + mn + span], original[base + fn:base + fn + span]
            for a, b in ((fh, mh), (fb, mb)):
                buf[base + a:base + a + 4], buf[base + b:base + b + 4] = \
                    original[base + b:base + b + 4], original[base + a:base + a + 4]
        if bytes(buf) != original:
            out.append(ln.Change(path, original, bytes(buf), "the Unaccounted roster"))
    return out


def write_save(folder: Path, game: int, slot: int, kind: additions.Kind, answers: dict[str, str],
               now: datetime | None = None) -> list[tools.WordFix]:
    """Write plan_save's files.  The caller refused a running game and backed the save folder up
    (vv_log_tools.approve_repair); each file is copied into Copies Made Before Repairs first, read back after it is
    written, and every one put back on a failure.  Returns one WordFix per file (its villagers swapped)."""
    import vv_last_names as ln
    folder = Path(folder)
    changes, who = plan_save(folder, game, slot, kind, answers)
    copies: dict[Path, str] = {}
    for change in changes:
        for k in range(1, 1000):
            target = tools.copy_before_repair(folder, change.path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
            if not target.exists():
                break
        else:
            raise tools.LogToolError(f"{change.path.name} has too many copies already; the parents were not "
                                     "swapped in it.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as copy:
            copy.write(change.original)
        copies[change.path] = target.name
    done: list = []
    try:
        for change in changes:
            if change.path.read_bytes() != change.original:
                raise tools.LogToolError(f"{change.path.name} changed while the parents were being swapped.")
            done.append(change)
            ln._write(change.path, change.updated)
            if change.path.read_bytes() != change.updated:
                raise tools.LogToolError(f"{change.path.name} did not read back as written.")
    except (OSError, tools.LogToolError, ln.LastNamesError) as exc:
        for change in reversed(done):
            try:
                ln._write(change.path, change.original)
            except (OSError, ln.LastNamesError):
                pass
        raise tools.LogToolError(f"The parents were not swapped in the save ({exc}); every file was put back.") from exc
    count = len(who)
    return [tools.WordFix(str(c.path.relative_to(folder)), count, copies[c.path]) for c in changes]
