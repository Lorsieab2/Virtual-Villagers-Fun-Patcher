"""Isola Grand Event Collection: the frozen source and the text rules the pipeline shares.

The owner's collection (v26) is frozen in the repo at SOURCE (its SHA-256 in data/event_collection/SOURCE.sha256), so
its line numbers are stable.  Every collection event file (data/event_collection/<section>/<id>.json) points back at
those lines with "src" tags ("L3070-3071", "L104,L106"); scripts/collection_check.py proves the file's text is the
source's text, word for word, apart from the mappings listed in docs/event-collection/authoring-rules.md.

This module only reads files.  Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "more-island-events" / \
    "Virtual_Villagers_Isola_Grand_Event_Collection_v26_user_source_credited.txt"
SOURCE_HASH_FILE = ROOT / "data" / "event_collection" / "SOURCE.sha256"
COLLECTION_DIR = ROOT / "data" / "event_collection"
MANIFEST = COLLECTION_DIR / "manifest.json"
SHARED_POOLS = COLLECTION_DIR / "shared_pools.json"
GRAMMAR_FIXES_DOC = ROOT / "docs" / "event-collection" / "grammar-fixes.md"
SOURCE_LINES = 10571


def source_sha256() -> str:
    return hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def recorded_sha256() -> str:
    """The hash recorded in SOURCE.sha256 ("<hex>  <path>")."""
    return SOURCE_HASH_FILE.read_text(encoding="ascii").split()[0].lower()


@lru_cache(maxsize=1)
def source_lines() -> tuple[str, ...]:
    """The source's lines; index 0 is line 1."""
    return tuple(SOURCE.read_text(encoding="utf-8").split("\n")[:SOURCE_LINES])


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
        if not 1 <= a <= b <= SOURCE_LINES:
            raise ValueError(f"src {spec!r}: lines {a}-{b} are outside 1..{SOURCE_LINES}")
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
]


def strip_structural(text: str) -> str:
    """One source line (already normalised) without its structural markers."""
    prev = None
    while prev != text:
        prev = text
        for rx in STRUCTURAL_INLINE:
            text = rx.sub(" " if rx.pattern.startswith(r"\b") else "", text)
    return text


WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")


def is_separator(s: str) -> bool:
    s = s.strip()
    return len(s) >= 5 and set(s) <= set("=-*_~")


def is_blank_or_separator(n: int) -> bool:
    s = line(n)
    return not s.strip() or is_separator(s)
