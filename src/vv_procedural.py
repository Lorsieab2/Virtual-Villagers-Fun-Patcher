"""Procedural island events (v1.35.97): the piece files (VPCB v1) and the Python TWIN of the run-time composer.

The contract is docs/event-collection/procedural-pieces.md (the engine's side is "VVFP Story Upgrades.dll").  This
module reads and writes the piece files and composes events from them exactly as section 3 orders the rolls, so the
same `random_below` stream gives the same choices as the engine.  Where the spec left a choice open, the rule this
twin follows is written in docs/event-collection/procedural-pieces-data.md ("The twin's readings"); the engine must
follow the same readings.

Nothing here touches a game, a save or an install.
"""
from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from typing import Callable, Iterable

MAGIC = b"VPCB"
VERSION = 1
HEADER_BYTES = 64
FILE_MAX = 1 << 20                      # the engine's sanity limit: 1 MB a file
NONE32 = 0xFFFFFFFF
EVERY = 0xFF                            # an effect's local slot: every villager (where the effect allows it)

KIND_SETUP, KIND_APPROACH, KIND_OUTCOME, KIND_FLAVOUR, KIND_FRAME = 1, 2, 3, 4, 5
KIND_NAMES = {1: "setup", 2: "approach", 3: "outcome", 4: "flavour", 5: "frame"}
MOODS = ("warm", "social", "serious")

PF_DEADLY = 1                           # piece flags
PF_BELIEVERS = 2
PF_AUTO_LINES = 4                       # an outcome: its effects told in automatic lines (cie-v6-binary.md 25)
PF_SOLIDARITY_SHIFT = 3                 # an outcome: its Village Solidarity tag, bits 3-4 (1 raise, 2 lower, 3 neutral;
PF_SOLIDARITY_MASK = 0x18               # the composed page's node flags bits 2-3: story_procedural.inc)
SOLIDARITY_CODES = {"raise": 1, "lower": 2, "neutral": 3}


def solidarity_flags(tag: str | None) -> int:
    """An outcome piece's flags bits for its ending's Village Solidarity tag (0: none)."""
    return SOLIDARITY_CODES.get(tag or "", 0) << PF_SOLIDARITY_SHIFT


def solidarity_of(flags: int) -> str | None:
    code = (flags & PF_SOLIDARITY_MASK) >> PF_SOLIDARITY_SHIFT
    return {v: k for k, v in SOLIDARITY_CODES.items()}.get(code)

SF_OPTIONAL, SF_BELIEVERS, SF_SPEAKS, SF_HARM, SF_CONVERSION, SF_ANY_BIRTH_SEX = 1, 2, 4, 8, 16, 32
SPECIAL_NONE, SPECIAL_GOLDEN_CHILD, SPECIAL_CHIEF, SPECIAL_CARRIER = 0, 1, 2, 3

# Tag bits (spec 2.3): the owner's four mixer blocks, then the data side's own.
TAG_POWER, TAG_INVALIDATING, TAG_LESSER, TAG_ROMANCE, TAG_MINOR = 1, 2, 4, 8, 16
TAG_ADULT_ROMANCE = 1 << 5              # data side: a romance piece whose romance roles are adults (age band 1)
FREE_BITS = tuple(range(6, 32))         # the validator's and the splitter's pair bits

AGE_BAND_ANY, AGE_BAND_ADULT, AGE_BAND_TEEN = 0, 1, 2

DEADLY_CODES = {4, 5, 18, 19, 20}       # kill, vanish, die_unrecovered, baby_lost, birth_then_die

_HEADER = struct.Struct("<4sHHIIBBHIIIIIIIIIII")
_PIECE = struct.Struct("<IBBBBIIIIIIIIIHHIHHIHH")
_SLOT = struct.Struct("<IBBBBBBHI")
_EFFECT = struct.Struct("<BBBBiiI")
_LINK = struct.Struct("<II")
assert (_HEADER.size, _PIECE.size, _SLOT.size, _EFFECT.size, _LINK.size) == (64, 64, 16, 16, 8)

ID_RE = re.compile(r"^[a-z0-9_]{1,100}$")
GROUP_RE = re.compile(r"^[a-z0-9_]{1,24}$")


@dataclass
class Slot:
    name: str
    kind: int = 0                       # 0 villager, 1 stranger
    sex: int = 0                        # 0 any, 1 male, 2 female
    min_age: int = 0
    max_age: int = 0                    # 0 none
    special: int = 0
    flags: int = 0


@dataclass
class Effect:
    code: int
    slot: int                           # local slot index, EVERY = every villager
    flags: int = 0
    a: int = 0
    b: int = 0
    string: str | None = None


@dataclass
class Link:
    approach: str
    weight: int = 1


@dataclass
class Piece:
    id: str
    kind: int
    mood: int = 0
    flags: int = 0
    games: int = 0x1F
    topic: int = 0
    family: int = 0
    filters: int = 0
    notes: int = 0
    never: int = 0
    tags: int = 0
    text: str | None = None
    label: str | None = None
    slots: list[Slot] = field(default_factory=list)
    weight: int = 1
    effects: list[Effect] = field(default_factory=list)
    age_band: int = 0
    links: list[Link] = field(default_factory=list)
    src: str = ""                       # authoring only (never written): where the piece came from


@dataclass
class PieceFile:
    group: str
    games: int
    pieces: list[Piece]

    def by_kind(self, kind: int) -> list[Piece]:
        return [p for p in self.pieces if p.kind == kind]


# ---- Writing and reading -------------------------------------------------------------------------------------------


def write_pcb(pieces: list[Piece]) -> bytes:
    """The file's bytes (spec 2), sections in this order: header, pieces, slots, effects, links, strings."""
    strings = bytearray()
    sidx: dict[str, int] = {}

    def s(text: str | None) -> int:
        if text is None:
            return NONE32
        if text not in sidx:
            raw = text.encode("ascii")
            if b"\0" in raw:
                raise ValueError("a NUL in a string")
            sidx[text] = len(strings)
            strings.extend(raw + b"\0")
        return sidx[text]

    ids = [p.id for p in pieces]
    if len(set(ids)) != len(ids):
        raise ValueError("piece ids are not unique")
    prec = bytearray()
    srec = bytearray()
    erec = bytearray()
    lrec = bytearray()
    ns = ne = nl = 0
    games = 0
    for p in pieces:
        if not ID_RE.match(p.id):
            raise ValueError(f"{p.id!r}: an id is [a-z0-9_]")
        if p.kind not in KIND_NAMES or not 0 <= p.mood <= 2 or not 1 <= p.weight <= 1000:
            raise ValueError(f"{p.id}: kind, mood or weight out of range")
        if (p.kind == KIND_SETUP and not (p.text and p.label)) or (p.kind == KIND_APPROACH and not p.label) \
                or (p.kind in (KIND_OUTCOME, KIND_FLAVOUR, KIND_FRAME) and not p.text) or len(p.slots) > 64:
            raise ValueError(f"{p.id}: a required text or label is missing, or more than 64 slots")
        games |= p.games
        fs, fe, fl = ns, ne, nl
        for sl in p.slots:
            srec += _SLOT.pack(s(sl.name), sl.kind, sl.sex, sl.min_age, sl.max_age, sl.special, sl.flags, 0, 0)
            ns += 1
        for e in p.effects:
            if e.code not in CODE_EFFECT:
                raise ValueError(f"{p.id}: effect code {e.code}")
            if e.slot not in (EVERY, *NEW_SLOTS) and not 0 <= e.slot < len(p.slots):
                raise ValueError(f"{p.id}: effect slot {e.slot}")
            erec += _EFFECT.pack(e.code, e.slot, e.flags, 0, e.a, e.b, s(e.string))
            ne += 1
        for lk in p.links:
            if not 1 <= lk.weight <= 1000:
                raise ValueError(f"{p.id}: link weight")
            lrec += _LINK.pack(s(lk.approach), lk.weight)
            nl += 1
        prec += _PIECE.pack(s(p.id), p.kind, p.mood, p.flags, p.games, p.topic, p.family, p.filters, p.notes,
                            p.never, p.tags, s(p.text), s(p.label), fs, len(p.slots), p.weight, fe,
                            len(p.effects), p.age_band, fl, len(p.links), 0)
    off_p = HEADER_BYTES
    off_s = off_p + len(prec)
    off_e = off_s + len(srec)
    off_l = off_e + len(erec)
    off_str = off_l + len(lrec)
    total = off_str + len(strings)
    body = bytes(prec + srec + erec + lrec + strings)

    def header(crc: int) -> bytes:
        return _HEADER.pack(MAGIC, VERSION, HEADER_BYTES, total, crc, games & 0x1F, 0, 0, len(pieces), off_p,
                            off_str, len(strings), off_e, ne, off_s, ns, off_l, nl, 0)
    crc = zlib.crc32(header(0) + body) & 0xFFFFFFFF
    data = header(crc) + body
    assert len(data) == total
    return data


class PcbError(ValueError):
    pass


def read_pcb(data: bytes, group: str = "") -> PieceFile:
    """The engine's reading (a damaged file is refused whole: PcbError)."""
    if len(data) < HEADER_BYTES or len(data) > FILE_MAX:
        raise PcbError("size")
    (magic, version, hbytes, total, crc, games, z1, z2, n_p, off_p, off_str, n_str, off_e, n_e, off_s, n_s, off_l,
     n_l, z3) = _HEADER.unpack_from(data, 0)
    if magic != MAGIC or version != VERSION or hbytes != HEADER_BYTES or total != len(data) or z1 or z2 or z3:
        raise PcbError("header")
    if zlib.crc32(data[:12] + b"\0\0\0\0" + data[16:]) & 0xFFFFFFFF != crc:
        raise PcbError("crc")
    for off, n, size in ((off_p, n_p, 64), (off_s, n_s, 16), (off_e, n_e, 16), (off_l, n_l, 8), (off_str, n_str, 1)):
        if off < HEADER_BYTES or off + n * size > total:
            raise PcbError("offsets")
    if n_str and data[off_str + n_str - 1] != 0:
        raise PcbError("strings")

    def s(off: int) -> str | None:
        if off == NONE32:
            return None
        if off >= n_str:
            raise PcbError("string offset")
        end = data.index(b"\0", off_str + off)
        return data[off_str + off:end].decode("ascii")

    pieces = []
    for i in range(n_p):
        (pid, kind, mood, flags, pgames, topic, family, filters, notes, never, tags, text, label, fs, cs, weight, fe,
         ce, band, fl, cl, z) = _PIECE.unpack_from(data, off_p + 64 * i)
        if fs + cs > n_s or fe + ce > n_e or fl + cl > n_l or kind not in KIND_NAMES or mood > 2:
            raise PcbError("counts")
        slots = [Slot(s(nm), k, sx, mn, mx, sp, fg) for nm, k, sx, mn, mx, sp, fg, _z, _z2 in
                 (_SLOT.unpack_from(data, off_s + 16 * j) for j in range(fs, fs + cs))]
        effects = [Effect(c, sl, fg, a, b, s(st)) for c, sl, fg, _z, a, b, st in
                   (_EFFECT.unpack_from(data, off_e + 16 * j) for j in range(fe, fe + ce))]
        links = [Link(s(ap), w) for ap, w in (_LINK.unpack_from(data, off_l + 8 * j) for j in range(fl, fl + cl))]
        pieces.append(Piece(s(pid), kind, mood, flags, pgames, topic, family, filters, notes, never, tags, s(text),
                            s(label), slots, weight, effects, band, links))
    return PieceFile(group, games, pieces)


# ---- Title case (the owner's rule) ----------------------------------------------------------------------------------

SMALL_WORDS = frozenset("a an the and but or nor of to in on at for by with from as".split())
_WORD = re.compile(r"\([^()]*\)|[^\s]+")


def _cap(word: str) -> str:
    for i, c in enumerate(word):
        if c.isalpha():
            return word[:i] + c.upper() + word[i + 1:]
    return word


def _core(word: str) -> str:
    return re.sub(r"[^a-z]", "", word.lower())


def title_case(text: str) -> str:
    """Every word capitalized except a, an, the, and, but, or, nor, of, to, in, on, at, for, by, with, from, as
    (unless first or last).  A text written all in capitals is lowered first; other letters stay as written."""
    if not text:
        return text
    letters = [c for c in re.sub(r"\([^()]*\)", "", text) if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        text = re.sub(r"\([^()]*\)|[A-Z]", lambda m: m.group(0) if len(m.group(0)) > 1 else m.group(0).lower(), text)
    words = text.split(" ")
    real = [i for i, w in enumerate(words) if any(c.isalpha() for c in w)]
    out = []
    for i, w in enumerate(words):
        if not w or not any(c.isalpha() for c in w):
            out.append(w)
            continue
        first, last = i == real[0], i == real[-1]
        if not w.startswith("(") and _core(w) in SMALL_WORDS and not first and not last:
            out.append(w.lower())
        elif w.startswith("("):
            # a placeholder: its capital form, the role prefix as written ("(friend.he/she)" -> "(friend.He/she)")
            close = w.find(")")
            inner = w[1:close] if close > 0 else w[1:]
            role, dot, word = inner.rpartition(".")
            out.append("(" + role + dot + _cap(word) + w[1 + len(inner):])
        else:
            out.append(_cap(w))
    return " ".join(out)


def title_case_ok(text: str) -> bool:
    return title_case(text) == text


# ---- The composer (spec 3) ------------------------------------------------------------------------------------------

RandomBelow = Callable[[int], int]


def compatible(p: Piece, q: Piece) -> bool:
    return not (p.never & q.tags) and not (q.never & p.tags)


@dataclass
class Settings:
    game: int
    filters: int = 0                    # ticked content filters (bit n-1: Fnn)
    gate: bool = False                  # the 61-villager gate holds (natural draw below 61 villagers, no No Safeguards)
    notes: bool = False                 # Content Notes on


def usable(p: Piece, st: Settings) -> bool:
    if not p.games & (1 << (st.game - 1)):
        return False
    if p.filters & st.filters:
        return False
    if st.gate and (p.flags & PF_DEADLY or any(e.code in DEADLY_CODES for e in p.effects)):
        return False
    if p.flags & PF_BELIEVERS and st.game != 5:
        return False
    return True


def weighted(cands: list, weights: list[int], random_below: RandomBelow):
    """Spec 3: total, r = random_below(total) (no roll when total <= 1), the first whose running sum passes r."""
    total = sum(weights)
    r = random_below(total) if total > 1 else 0
    run = 0
    for c, w in zip(cands, weights):
        run += w
        if run > r:
            return c
    return cands[-1]


@dataclass
class Merged:
    name: str
    kind: int
    sex: int
    min_age: int
    max_age: int
    special: int
    flags: int
    optional: bool = True
    users: list[str] = field(default_factory=list)      # piece ids that declare it


def merge_slots(pieces: Iterable[tuple[Piece, bool]]) -> tuple[dict[str, Merged] | None, str]:
    """Spec 2.4: one role per name; the larger min age, the smaller max age, flags OR'ed except bit 0; sexes and
    specials agree or one is 0; kinds agree.  pieces: (piece, is an outcome).  The role is optional only when every
    slot merged into it is optional or an outcome's own.  (None, why) when a merge cannot hold."""
    out: dict[str, Merged] = {}
    for p, is_outcome in pieces:
        for sl in p.slots:
            opt = bool(sl.flags & SF_OPTIONAL) or is_outcome
            m = out.get(sl.name)
            if m is None:
                out[sl.name] = Merged(sl.name, sl.kind, sl.sex, sl.min_age, sl.max_age, sl.special,
                                      sl.flags & ~SF_OPTIONAL, opt, [p.id])
                continue
            if m.kind != sl.kind:
                return None, f"{sl.name}: villager and stranger"
            if m.sex and sl.sex and m.sex != sl.sex:
                return None, f"{sl.name}: sexes differ"
            if m.special and sl.special and m.special != sl.special:
                return None, f"{sl.name}: specials differ"
            m.sex = m.sex or sl.sex
            m.special = m.special or sl.special
            m.min_age = max(m.min_age, sl.min_age)
            if sl.max_age:
                m.max_age = min(m.max_age, sl.max_age) if m.max_age else sl.max_age
            m.flags |= sl.flags & ~SF_OPTIONAL
            m.optional = m.optional and opt
            m.users.append(p.id)
            if m.max_age and m.min_age > m.max_age:
                return None, f"{sl.name}: ages {m.min_age}..{m.max_age}"
    return out, ""


@dataclass
class Composition:
    group: str
    setup: Piece
    approaches: list[Piece]
    outcomes: list[list[Piece]]          # per kept approach, in pick order
    flavour: Piece | None
    frame: Piece | None
    roles: dict[str, Merged]
    cast: dict[str, object]
    rejected: list[tuple[str, str]] = field(default_factory=list)   # (setup id, why) of earlier attempts
    note_bits: int = 0
    dropped: list[Piece] = field(default_factory=list)              # approaches left out at step 6

    def pieces(self) -> list[Piece]:
        out = [self.setup] + list(self.approaches) + [o for os in self.outcomes for o in os]
        return out + [p for p in (self.flavour, self.frame) if p is not None]


CastFn = Callable[[list[Merged]], "dict[str, object] | None"]   # merged roles -> {name: villager}; None: cast fails

MAX_SETUP_TRIES = 8


def needed(p: Piece | None) -> set[str]:
    return set() if p is None else {sl.name for sl in p.slots if not sl.flags & SF_OPTIONAL}


def plain(o: Piece, setup: Piece, approach: Piece, flavour: Piece | None, frame: Piece | None) -> bool:
    """Spec 3 step 6: every slot the outcome declares is a needed slot of the setup, its approach, the flavour line
    or the frame."""
    have = needed(setup) | needed(approach) | needed(flavour) | needed(frame)
    return all(sl.name in have for sl in o.slots)


def compose(pf: PieceFile, st: Settings, random_below: RandomBelow, cast: CastFn | None = None,
            check: Callable[[Composition], str] | None = None, trace: list | None = None,
            fixed_setup: str | None = None) -> Composition | None:
    """Spec 3, steps 1-8 (for one file).  `cast` stands in for the engine's casting (step 6: it gets the merged roles
    in merge order and returns who takes each, or None when the cast fails); `check` stands in for step 7's cg_load
    (returns a problem or "").  trace, when given, gets (step, detail) for every attempt.  fixed_setup: Pick Island
    Event and the library (the 8 tries keep that setup)."""
    setups = [p for p in pf.pieces if p.kind == KIND_SETUP]
    approaches = [p for p in pf.pieces if p.kind == KIND_APPROACH]
    outcomes = [p for p in pf.pieces if p.kind == KIND_OUTCOME]
    flavours = [p for p in pf.pieces if p.kind == KIND_FLAVOUR]
    frames = [p for p in pf.pieces if p.kind == KIND_FRAME]
    answered = {lk.approach for o in outcomes if usable(o, st) for lk in o.links}
    left_out: set[str] = set()
    rejected: list[tuple[str, str]] = []

    def say(step, detail):
        if trace is not None:
            trace.append((step, detail))

    for _attempt in range(MAX_SETUP_TRIES):
        cands = [p for p in setups if usable(p, st) and p.id not in left_out
                 and (fixed_setup is None or p.id == fixed_setup)]
        if not cands:
            break
        setup = weighted(cands, [p.weight for p in cands], random_below)            # roll 1
        say(1, setup.id)

        def reject(why: str):
            if fixed_setup is None:
                left_out.add(setup.id)
            rejected.append((setup.id, why))
            say("rejected", why)

        # 2. Approaches
        n = 2 + random_below(3)                                                       # roll 2, always made
        chosen: list[Piece] = []
        for _ in range(n):
            pool = [a for a in approaches if usable(a, st) and a.family == setup.family and a not in chosen
                    and a.id in answered and all(compatible(a, q) for q in [setup] + chosen)]
            if not pool:
                break
            chosen.append(weighted(pool, [a.weight for a in pool], random_below))
        say(2, [a.id for a in chosen])
        if len(chosen) < 2:
            reject("fewer than 2 approaches")
            continue
        # 3. Outcomes
        picked: list[list[Piece]] = []
        for a in chosen:
            m = 1 + random_below(3)                                                   # always made
            linked = []
            for o in outcomes:
                if not usable(o, st) or not compatible(o, setup) or not compatible(o, a):
                    continue
                w = next((lk.weight for lk in o.links if lk.approach == a.id), 0)
                if w:
                    linked.append((o, w))
            mine: list[Piece] = []
            for _ in range(m):
                if not linked:
                    break
                o, _w = weighted(linked, [w for _o, w in linked], random_below)
                linked = [x for x in linked if x[0] is not o]
                mine.append(o)
            picked.append(mine)
        say(3, [[o.id for o in os] for os in picked])
        so_far = [setup] + chosen + [o for os in picked for o in os]
        # 4. Flavour, 5. Frame
        flavour = frame = None
        if random_below(100) < 50:
            pool = [f for f in flavours if usable(f, st) and f.mood == setup.mood
                    and all(compatible(f, q) for q in so_far)]
            if pool:
                flavour = weighted(pool, [f.weight for f in pool], random_below)
                so_far.append(flavour)
        if random_below(100) < 30:
            pool = [f for f in frames if usable(f, st) and all(compatible(f, q) for q in so_far)]
            if pool:
                frame = weighted(pool, [f.weight for f in pool], random_below)
        say(5, (flavour.id if flavour else None, frame.id if frame else None))
        # 6. Keep and cast
        keep_a, keep_o, dropped = [], [], []
        for a, os in zip(chosen, picked):
            if any(plain(o, setup, a, flavour, frame) for o in os):
                keep_a.append(a)
                keep_o.append(os)
            else:
                dropped.append(a)
        if len(keep_a) < 2:
            reject("fewer than 2 approaches with a plain outcome")
            continue
        order = [(setup, False)] + [(a, False) for a in keep_a] + [(p, False) for p in (flavour, frame) if p] \
            + [(o, True) for os in keep_o for o in os]
        roles, why = merge_slots(order)
        if roles is None:
            reject("merge: " + why)
            continue
        if not any(m.kind == 0 and not m.optional for m in roles.values()) \
                and not any(m.kind == 1 for m in roles.values()):
            reject("no needed villager and no stranger")
            continue
        if len(roles) > 16:
            reject("more than 16 roles")
            continue
        bound = cast(list(roles.values())) if cast else {r: r for r in roles}
        if bound is None:
            reject("cast")
            continue
        comp = Composition(pf.group, setup, keep_a, keep_o, flavour, frame, roles, bound, list(rejected),
                           dropped=dropped)
        for p in comp.pieces():
            comp.note_bits |= p.notes
        if check is not None:
            problem = check(comp)
            if problem:
                reject("graph: " + problem)
                continue
        return comp
    return None


# ---- Step 7: the graph the engine writes --------------------------------------------------------------------------

NOTE_LABELS = ("Child death", "Pregnancy loss", "Bereavement", "Serious injury", "Disappearance",
               "Historical suffering", "Emotional distress")    # vv_event_content.NOTE_LABELS, in its order

CODE_EFFECT = {1: "food", 2: "tech", 3: "pay_award", 4: "kill", 5: "vanish", 6: "status", 7: "health",
               8: "preference", 9: "skill", 10: "sick", 11: "celebrate", 12: "action", 13: "mood",
               14: "health_change", 15: "skill_set", 16: "damage", 17: "appearance", 18: "die_unrecovered",
               19: "baby_lost", 20: "birth_then_die", 21: "old_look", 22: "sex_change", 23: "presentation",
               24: "deliver_early", 26: "trait", 27: "new_villager", 28: "pregnant", 29: "nursing", 30: "clone",
               31: "body_swap", 32: "lose_name", 33: "change_name", 34: "change_age", 35: "cure", 36: "repair",
               37: "young_look"}    # vv_cie_graph.EFFECT_CODES (code 25 is reserved)
NEW_SLOTS = {253: "$newest", 252: "$previous"}   # an effect's slot: the villagers the event itself made
NEW_VILLAGER_AGES = {0: "any", 1: "child", 2: "teen", 3: "adult", 4: "elder"}
NEW_VILLAGER_SEX = {0: "random", 1: "male", 2: "female"}
CHANGE_AGE_TO = {0: "child", 1: "teen", 2: "18", 3: "adult", 4: "50", 5: "elder"}
TRAITS = {1: "mute"}
BABIES = {2: "roll", 4: 2, 6: 3}


def effect_json(e: Effect, names: list[str]) -> dict:
    """An effect record as graph JSON, its local slots named (the .cieg decoding, cie-v6-binary.md)."""
    import vv_cie_graph as cg

    def rn(i: int) -> str:
        return NEW_SLOTS[i] if i in NEW_SLOTS else names[i]
    do = CODE_EFFECT[e.code]
    role = None if e.slot == EVERY else rn(e.slot)
    out: dict = {"do": "skill" if do == "skill_set" else do}
    if do in ("food", "tech"):
        out.update(amount=e.a, scaled=bool(e.flags & 1), defer=bool(e.flags & 2))
        if e.b:
            out["max"] = e.b
        if e.string is not None:
            out["per_game"] = cg.per_game_parse(e.string)
    elif do == "celebrate":
        out["who"] = "all" if role is None else role
    elif do == "damage":
        out.update(structures="any" if e.string == "any" else (e.string or "").split(","), min=e.a, max=e.b)
    elif do == "repair":
        out["structures"] = "any" if e.string == "any" else (e.string or "").split(",")
    elif do == "new_villager":
        if role is not None:
            out["copy_of"] = role
        if NEW_VILLAGER_AGES[e.a] != "any":
            out["age"] = NEW_VILLAGER_AGES[e.a]
        if NEW_VILLAGER_SEX[e.b] != "random":
            out["sex"] = NEW_VILLAGER_SEX[e.b]
        if e.flags & 1:
            out["child_of_newest"] = True
    elif do != "pay_award":
        out["role"] = role
        if do == "kill":
            out["cause"] = e.string
        elif do == "status":
            out["status"] = "heathen"
        elif do in ("health", "health_change"):
            out.update(min=e.a, max=e.b)
            if do == "health_change" and e.flags & 1:
                out["restore"] = True          # cie-v6-binary.md 25a
        elif do == "preference":
            out.update(list="dislikes" if e.flags & 4 else "likes", preference="random" if e.flags & 8 else e.string)
            if e.flags & 16:
                out["remove"] = True
        elif do in ("skill", "skill_set"):
            out.update(skills=(e.string or "").split(","))
            out.update(dict(min=e.a, max=e.b) if do == "skill" else dict(set=e.a))
            if e.flags & 32:
                out["best"] = True
        elif do == "action":
            out["action"] = e.string
        elif do == "mood":
            out["mood"] = "good" if e.a > 0 else "bad"
        elif do == "appearance":
            for part, v in (("head", e.a), ("body", e.b)):
                if v != -2:
                    out[part] = "random" if v == -1 else v
        elif do in ("die_unrecovered", "birth_then_die"):
            out["cause"] = e.string
        elif do == "deliver_early" and (e.a or e.b):
            out.update(min=e.a, max=e.b)
        elif do in ("pregnant", "nursing"):
            if e.a != EVERY:
                out["partner"] = rn(e.a)
            if e.flags & 1:
                out["any_birth_sex"] = True
            if e.flags & 6:
                out["babies"] = BABIES[e.flags & 6]
            if e.flags & 8:          # the partner may carry (vv_cie_graph.PARTNER_MAY_CARRY_FLAG)
                out["partner_may_carry"] = True
        elif do == "body_swap":
            out["with"] = rn(e.a)
        elif do == "change_name" and e.string:
            out["name"] = e.string
        elif do == "clone" and e.a == 2:
            out["count"] = 2
        elif do == "change_age":
            if e.flags == 6:
                out["years"] = [e.a, e.b]
            else:
                out["to"] = CHANGE_AGE_TO[e.flags]
        elif do == "trait":
            out["trait"] = TRAITS[e.a]
        elif do == "presentation":
            out["on"] = e.a == 1
    return out


def note_line(bits: int) -> str:
    return "Content note: " + ", ".join(lab for k, lab in enumerate(NOTE_LABELS) if bits >> k & 1)


SEX_WORDS = {0: "any", 1: "male", 2: "female"}
SPECIAL_WORDS = {1: "golden_child", 2: "tribal_chief"}


def role_json(m: Merged) -> dict:
    """Spec 2.4: how a merged role is written in the .cieg (as graph JSON)."""
    if m.kind == 1:
        return {"kind": "stranger", "sex": "random" if not m.sex else SEX_WORDS[m.sex], "named": True}
    sex = m.sex
    min_age = m.min_age
    if m.special == SPECIAL_CARRIER:
        min_age = max(min_age, 18)
        if not m.flags & SF_ANY_BIRTH_SEX and not sex:
            sex = 2
    r: dict = {"kind": "villager", "sex": SEX_WORDS[sex], "min_age": min_age}
    if m.max_age:
        r["max_age"] = m.max_age
    if m.special in SPECIAL_WORDS:
        r["special"] = SPECIAL_WORDS[m.special]
        r["protected"] = "allow"
    if m.optional:
        r["optional"] = True
    r["believers_only"] = not m.flags & SF_CONVERSION
    if m.flags & SF_SPEAKS:
        r["speaks"] = True
    return r


def graph_of(comp: Composition, game: int, notes: bool = False) -> dict:
    """Spec 3 step 7: the version 6 graph the engine writes in memory (as JSON, for vv_cie_graph's checks).  The
    collection block ({"procedural": ...}) is left out here: vv_cie_graph's collection checks are for files."""
    paras = []
    if notes and comp.note_bits:
        paras.append(note_line(comp.note_bits))
    if comp.flavour is not None and comp.flavour.text:
        paras.append(comp.flavour.text)
    paras.append(comp.setup.text or "")
    if comp.frame is not None and comp.frame.text:
        paras.append(comp.frame.text)
    # the first role: the first needed villager role, else the first stranger (2.4)
    order = list(comp.roles)
    first = next((r for r in order if comp.roles[r].kind == 0 and not comp.roles[r].optional),
                 next((r for r in order if comp.roles[r].kind == 1), None))
    if first is not None:
        order.remove(first)
        order.insert(0, first)
    roles = {name: role_json(comp.roles[name]) for name in order}
    # the start popup and its question are one node (a v6 question shows its text above its buttons)
    nodes: dict = {"q": {"type": "question", "text": "\n\n".join(p for p in paras if p), "choices": []}}
    for i, (a, os) in enumerate(zip(comp.approaches, comp.outcomes), 1):
        nodes["q"]["choices"].append({"label": a.label or "", "next": f"a{i}"})
        kids = []
        for j, o in enumerate(os, 1):
            nid = f"o{i}_{j}"
            kid: dict = {"next": nid, "weight": next(lk.weight for lk in o.links if lk.approach == a.id)}
            opt = [sl.name for sl in o.slots if comp.roles[sl.name].optional]
            if opt:
                conds = [{"role": r} for r in dict.fromkeys(opt)]
                kid["if"] = conds[0] if len(conds) == 1 else {"all": conds}
            kids.append(kid)
            names = [sl.name for sl in o.slots]
            node: dict = {"type": "popup", "popup": "append" if a.text else "new", "join": "paragraph",
                          "text": o.text or ""}
            fx = [effect_json(e, names) for e in o.effects]
            if fx:
                node["effects"] = fx
            if o.flags & PF_AUTO_LINES:
                node["auto_text"] = True
            if solidarity_of(o.flags):
                node["solidarity"] = solidarity_of(o.flags)
            nodes[nid] = node
        if a.text:
            # its own popup after the question's (nothing is open to append to once an answer is clicked)
            nodes[f"a{i}"] = {"type": "popup", "popup": "new", "join": "paragraph", "text": a.text,
                              "children": kids}
        else:
            nodes[f"a{i}"] = {"type": "branch", "children": kids}
    return {"format": "vvfp-cie-graph", "version": 6, "title": comp.setup.label or "",
            "games": [game], "roles": roles, "start": "q", "nodes": nodes}


# ---- A reference random stream (for the validator and the samples; the game uses its own) -------------------------


class Lcg:
    """A small deterministic stream with ce_random_below's contract: no roll when n <= 1."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF
        self.rolls = 0

    def __call__(self, n: int) -> int:
        if n <= 1:
            return 0
        self.state = (self.state * 1103515245 + 12345) & 0xFFFFFFFF
        self.rolls += 1
        return ((self.state >> 8) * n) >> 24
