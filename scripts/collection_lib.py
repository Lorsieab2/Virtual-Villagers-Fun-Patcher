"""Isola Grand Event Collection: the frozen source and the text rules the pipeline shares.

The owner's collection (V28, 2026-11-14; it replaced the v26 file, whose lines 1-10431 it keeps apart from four word
edits) is frozen in the repo at SOURCE (its SHA-256 in data/event_collection/SOURCE.sha256), so
its line numbers are stable.  Every collection event file (data/event_collection/<section>/<id>.json) points back at
those lines with "src" tags ("L3070-3071", "L104,L106"); scripts/collection_check.py proves the file's text is the
source's text, word for word, apart from the mappings listed in docs/event-collection/authoring-rules.md.

TWO SOURCES (2026-11-14).  The owner's Companion Anthology (749 events in five volumes) is a second frozen source,
COMPANION (its SHA-256 in data/event_collection/COMPANION.sha256).  Each collection file's `collection.source` names
its source ("v28" or "companion": the manifest row's `source`), and every "src" tag of that file means lines of THAT
source.  The functions below read the ACTIVE source: SOURCE_ID unless a caller wraps its work in
`with use_source("companion"):` (scripts/collection_check.py does so per file, collection_manifest.py per row).

This module only reads files.  Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "more-island-events" / \
    "Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt"
SOURCE_HASH_FILE = ROOT / "data" / "event_collection" / "SOURCE.sha256"
COLLECTION_DIR = ROOT / "data" / "event_collection"
MANIFEST = COLLECTION_DIR / "manifest.json"
SHARED_POOLS = COLLECTION_DIR / "shared_pools.json"
GRAMMAR_FIXES_DOC = ROOT / "docs" / "event-collection" / "grammar-fixes.md"
SOURCE_LINES = 11125
SOURCE_ID = "v28"           # the Grand collection's files' collection.source
OWNER_TITLES_DOC = ROOT / "docs" / "event-collection" / "owner-title-changes.md"

# The second source: the owner's Companion Anthology (frozen byte for byte from the owner's file, 2026-11-14).
COMPANION = ROOT / "docs" / "more-island-events" / "Isola_COMPLETE_Master_Companion_Anthology_749_Events.txt"
COMPANION_HASH_FILE = COLLECTION_DIR / "COMPANION.sha256"
COMPANION_LINES = 8961
COMPANION_ID = "companion"  # the companion files' collection.source
COMPANION_DIR = COLLECTION_DIR / "companion"     # data/event_collection/companion/<volume>/<id>.json

# source id -> (frozen file, its SHA-256 record, its line count)
SOURCES = {SOURCE_ID: (SOURCE, SOURCE_HASH_FILE, SOURCE_LINES),
           COMPANION_ID: (COMPANION, COMPANION_HASH_FILE, COMPANION_LINES)}
_ACTIVE = [SOURCE_ID]


@contextmanager
def use_source(source_id: str):
    """Within the block, line(), src tags and the structural markers mean `source_id`'s lines."""
    if source_id not in SOURCES:
        raise ValueError(f"unknown source {source_id!r} (known: {', '.join(SOURCES)})")
    _ACTIVE.append(source_id)
    try:
        yield
    finally:
        _ACTIVE.pop()


def active_source() -> str:
    return _ACTIVE[-1]


def n_lines(source_id: str | None = None) -> int:
    """The active (or named) source's line count."""
    return SOURCES[source_id or active_source()][2]


def source_path(source_id: str | None = None) -> Path:
    return SOURCES[source_id or active_source()][0]


@lru_cache(maxsize=None)
def owner_titles() -> dict[str, dict[str, str]]:
    """The owner's title changes (docs/event-collection/owner-title-changes.md): {id: {"old", "new", "date", "by"}}.
    Each row is "| `id` | old | new | date | by |"; the titles are kept exactly as written there."""
    out: dict[str, dict[str, str]] = {}
    for row in OWNER_TITLES_DOC.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"\| `([a-z0-9_]+)` \| (.+?) \| (.+?) \| (\d{4}-\d{2}-\d{2}) \| (\w+) \|", row.strip())
        if m:
            out[m.group(1)] = {"old": m.group(2), "new": m.group(3), "date": m.group(4), "by": m.group(5)}
    return out


GUARDIANS_DOC = ROOT / "docs" / "event-collection" / "guardians-wording.md"


@lru_cache(maxsize=None)
def guardians_pairs() -> dict[str, list[tuple[str, str, str]]]:
    """The Guardians of Isola Rewrite wording (docs/event-collection/guardians-wording.md): {id: [(where, before,
    after), ...]}, from each row "| `id` | where | before | after |" of its collection table."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for row in GUARDIANS_DOC.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"\| `([a-z0-9_]+)` \| (.+?) \| (.+?) \| (.+?) \|", row.strip())
        if m:
            out.setdefault(m.group(1), []).append((m.group(2), m.group(3), m.group(4)))
    return out


def source_sha256(source_id: str = SOURCE_ID) -> str:
    return hashlib.sha256(SOURCES[source_id][0].read_bytes()).hexdigest()


def recorded_sha256(source_id: str = SOURCE_ID) -> str:
    """The hash recorded in SOURCE.sha256 / COMPANION.sha256 ("<hex>  <path>")."""
    return SOURCES[source_id][1].read_text(encoding="ascii").split()[0].lower()


@lru_cache(maxsize=None)
def _lines_of(source_id: str) -> tuple[str, ...]:
    path, _, count = SOURCES[source_id]
    return tuple(path.read_text(encoding="utf-8").split("\n")[:count])


def source_lines(source_id: str | None = None) -> tuple[str, ...]:
    """The active (or named) source's lines; index 0 is line 1."""
    return _lines_of(source_id or active_source())


def line(n: int) -> str:
    return source_lines()[n - 1]


# ---- src tags --------------------------------------------------------------------------------------------------------

SRC_RE = re.compile(r"^L(\d+)(?:-(\d+))?$")


def parse_src(spec: str) -> list[tuple[int, int]]:
    """'L3070-3071,L3080' -> [(3070, 3071), (3080, 3080)].  Raises ValueError on a malformed tag."""
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError(f"src {spec!r} is not a tag like 'L3070-3071'")
    out = []
    for part in spec.split(","):
        m = SRC_RE.match(part.strip())
        if not m:
            raise ValueError(f"src {spec!r}: {part.strip()!r} is not 'L<line>' or 'L<first>-<last>'")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if not 1 <= a <= b <= n_lines():
            raise ValueError(f"src {spec!r}: lines {a}-{b} are outside 1..{n_lines()} of the {active_source()} source")
        out.append((a, b))
    return out


def src_lines(spec: str) -> list[int]:
    return [n for a, b in parse_src(spec) for n in range(a, b + 1)]


def fmt_src(a: int, b: int) -> str:
    return f"L{a}" if a == b else f"L{a}-{b}"


# ---- Authoring normalisation (design A5, collection_decisions Q10) ----------------------------------------------------
#
# The source uses typographic characters no game's island-event text holds.  Authoring writes them as below; the
# fidelity check applies the same table to the source before comparing, so these are never counted as edits.  The
# characters a v6 text may hold are the CIE set plus ; / & % and the escaped parentheses \( \) (design A5); the
# VV1/VV2 display fallback for ; ( ) & % is the engine's (cg_glyph_fallback) and needs nothing from the author.

NORMALIZE = (
    ("—", " - "),     # em dash
    ("–", "-"),       # en dash (VV1-VV5 ranges; never prose in this source)
    ("‘", "'"), ("’", "'"),
    ("“", '"'), ("”", '"'),
    ("…", "..."),
    ("ç", "c"), ("é", "e"),
)

# The display-time glyph fallback the engine applies in A New Home and The Lost Children when the Unicode Text
# companion is not installed (design A5).  Listed for the owner packet; the author writes the real character.
FONT_FALLBACK_VV12 = {";": ",", "(": "-", ")": "-", "&": "and", "%": " percent"}


def normalize_source_text(text: str) -> str:
    for a, b in NORMALIZE:
        text = text.replace(a, b)
    return text


def substitutions_in(text: str) -> list[str]:
    """The authoring substitutions a source text needs (for the ledger / owner packet)."""
    return [f"{a!r} -> {b!r}" for a, b in NORMALIZE if a in text]


# ---- Structural markers (design E3: "strip structural markers only") -------------------------------------------------
#
# These are the only source words an author may leave out without a ledger entry: choice prefixes, outcome letters,
# bullets, route numbers, "choose one", "Go to (n)", game-limit tags on a choice.  Everything else that is not shown
# must be listed in the event's ledger (structural line, designer note, instruction or bank reference).

STRUCTURAL_INLINE = [
    re.compile(r"^\s*CHOICE\s*[A-Z]?\s*(?::|\s-\s|\s*-)\s*"),                # CHOICE A: / CHOICE A - / CHOICE:
    re.compile(r"^\s*[-*]\s+"),                                              # bullets
    re.compile(r"^\s*[A-G]\d{0,2}\s*(?:\.|:|\s-\s)\s*(?=\S)"),               # A. / A: / A1 - / B2:
    re.compile(r"^\s*\(\d+\)\s*:?\s*$"),                                     # a bank heading "(3)" / "(4):" alone
    re.compile(r"^\s*\(\d+\)\s*(?=\S)"),                                     # (3) at the start of a line
    re.compile(r"\(\s*(?:VV\d(?:\s*-\s*VV\d)?[,\s]*)+ONLY\s*\)"),            # (VV3-VV5 ONLY)
    re.compile(r"\bGo to \(\d+\)\.?"),                                       # Go to (5).
    re.compile(r"\s+\(\d+\)\s*\.?\s*$"),                                     # a trailing route (3)
    re.compile(r"\s*-?\s*choose one:?\s*$", re.I),
    re.compile(r"^\s*(?:SETUP|OUTCOME\s+[A-C])\s*:\s*"),                     # V27: SETUP: / OUTCOME A:
]


# The Companion Anthology's own structural markers (its event formats, docs/event-collection/companion-authoring.md),
# used only for that source so no Grand collection line changes meaning.  Each is a label in front of the owner's
# words, never words of the scene: an outcome's or response's number, a page label, a bullet.
COMPANION_STRUCTURAL = [
    re.compile(r"^\s*•\s+"),                                                 # • bullets (Vol 1 Parts 2 and 3)
    re.compile(r"^\s*RANDOM OUTCOME \d+\s+-\s+"),                            # Vol 1 Part 1: RANDOM OUTCOME 1 -
    re.compile(r"^\s*WEIGHTED OUTCOME \d+\s*:\s*"),                          # Vol 2: WEIGHTED OUTCOME 1:
    re.compile(r"^\s*PLAYER RESPONSE [A-D]\s+-\s+"),                         # Vol 2: PLAYER RESPONSE A -
    re.compile(r"^\s*(?:SCENE|Premise|OUTCOME|Outcome)\s*:\s*"),             # Vol 2 SCENE:, Vols 3-5 Premise: / Outcome:
    re.compile(r"^\s*\d{1,2}\.\s+(?=\S)"),                                   # Vol 1 Parts 4-5: numbered outcomes, options
]


def structural_markers() -> list[re.Pattern]:
    """The structural markers of the active source."""
    return STRUCTURAL_INLINE + (COMPANION_STRUCTURAL if active_source() == COMPANION_ID else [])


def strip_structural(text: str) -> str:
    """One source line (already normalised) without its structural markers."""
    prev = None
    while prev != text:
        prev = text
        for rx in structural_markers():
            text = rx.sub(" " if rx.pattern.startswith(r"\b") else "", text)
    return text


WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")


def is_separator(s: str) -> bool:
    s = s.strip()
    return len(s) >= 5 and set(s) <= set("=-*_~")


def is_blank_or_separator(n: int) -> bool:
    s = line(n)
    return not s.strip() or is_separator(s)
