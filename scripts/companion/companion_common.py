"""Shared helpers for the Companion Anthology generators (scripts/companion/gen_<part>.py).

The Companion Anthology is the collection's second frozen source (collection_lib.COMPANION; its own line numbers).
A generator reads its event rows from data/event_collection/manifest.json ("source": "companion"), writes one v6 file
per event to data/event_collection/companion/<section>/<id>.json and runs scripts/collection_check.py --format on
them.  The rules every generator follows are docs/event-collection/companion-authoring.md.

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402

ALL = [1, 2, 3, 4, 5]

# Roles (the authoring rules' ages; ELDER is the collection's elder age, 55, as in V27)
VILLAGER = {"kind": "villager", "min_age": 14}
GROWN = {"kind": "villager", "min_age": 18}
CHILD = {"kind": "villager", "min_age": 3, "max_age": 13}
TEEN = {"kind": "villager", "min_age": 14, "max_age": 17}
ELDER = {"kind": "villager", "min_age": 55}
ANY_AGE = {"kind": "villager", "min_age": 3}


def skilled(base: dict, skill: str) -> dict:
    """A role the text names by trade ("a healer", "a respected builder"): at least 1 in that skill."""
    return dict(base, skill={"names": [skill], "min": 1})


def sexed(base: dict, sex: str) -> dict:
    return dict(base, sex=sex)


def related(base: dict, kind: str, other: str) -> dict:
    """Kinship the text states ("his child", "two siblings"): cie-v6-binary.md 21."""
    return dict(base, relation={kind: other})


# Effects (each gets the src of the line it belongs to)
def skill(role: str, skills, size: str = "small") -> dict:
    lo, hi = cc.SKILL_SIZES[size]
    return {"do": "skill", "role": role, "skills": [skills] if isinstance(skills, str) else list(skills),
            "min": lo, "max": hi}


def parenting(role: str) -> dict:
    """The volumes' rule: a child's caregiver gains Parenting on every outcome (small: a quiet everyday scene)."""
    return skill(role, "Parenting")


def celebrate_all() -> dict:
    return {"do": "celebrate", "who": "all"}


def text_only(what: str, reason: str) -> dict:
    return {"what": what, "reason": reason}


# Source access -------------------------------------------------------------------------------------------------------

def rows(prefix: str) -> list[dict]:
    """The manifest's companion event rows whose id starts with `prefix`, in source order."""
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    out = [r for r in data["rows"] if r.get("source") == lib.COMPANION_ID and r["kind"] == "event"
           and r["id"].startswith(prefix)]
    return sorted(out, key=lambda r: r["lines"][0])


def num_of(row: dict) -> int:
    return int(re.match(r"[a-z]+?(\d+)_", re.sub(r"^c5[a-e][nv]?", "x", row["id"])).group(1))


def line(n: int) -> str:
    with lib.use_source(lib.COMPANION_ID):
        return lib.normalize_source_text(lib.line(n))


def heading_line(row: dict, rx: str) -> int:
    """The event's own heading line inside its row (the row may start at a group heading above it)."""
    a, b = row["lines"]
    for n in range(a, b + 1):
        if re.match(rx, line(n)):
            return n
    raise SystemExit(f"{row['id']}: no heading {rx!r} in L{a}-{b}")


def group_heading_ledger(row: dict, head: int) -> list[dict]:
    """The group heading lines above the event ("POTTERY" between its rules): structural, never shown."""
    out = []
    for n in range(row["lines"][0], head):
        s = line(n).strip()
        if s and not lib.is_separator(s):
            out.append({"src": f"L{n}", "kind": "structural", "why": f"the group heading {s!r}"})
    return out


def shown(n: int, cuts: dict[int, list[str]] | None = None) -> str:
    """Line n as a page shows it: typography, the ledger's cuts and the structural markers applied."""
    with lib.use_source(lib.COMPANION_ID):
        p = cc.processed_line(n, cuts or {}, {})
    return p[:1].upper() + p[1:]


def L(n: int) -> str:
    return f"L{n}"


def with_src(items: list[dict], src: str) -> list[dict]:
    return [dict(x, src=src) for x in items]


def page(name: str, text: str, src: str, effects=(), text_only_=(), append: bool = False) -> dict:
    node: dict = {"name": name}
    if append:
        node.update(popup="append", join="paragraph")
    node.update(text=text, src=src)
    if effects:
        node["effects"] = with_src(list(effects), src)
    if text_only_:
        node["text_only"] = with_src(list(text_only_), src)
    return node


def description_ok(text: str) -> bool:
    return bool(cc.DESCRIPTION_RE.fullmatch(text)) and len(text) <= cc.DESCRIPTION_MAX


def write_and_check(docs: list[tuple[str, str, dict]]) -> int:
    """Write each (section, id, doc) and run collection_check --format on them all."""
    paths = []
    for section, eid, doc in docs:
        p = lib.COMPANION_DIR / section / f"{eid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
