"""Shared helpers for the Living Event Engine's fixed event volumes (scripts/living_vols/gen_<chunk>.py).

The owner's all-in-one Living Event Engine file is the collection's THIRD frozen source (collection_lib.LIVING; its
own line numbers).  Its fixed event volumes (MED-, LIFE-, CIRCLE-, PEOPLES-, ...) are collection events like the
Companion Anthology's: one v6 file per event in data/event_collection/living/<section>/<id>.json, rows from
data/event_collection/manifest.json ("source": "living"), checked by scripts/collection_check.py --format.

THE EVENT SHAPE (every volume these helpers build):
  <PREFIX>-NN — TITLE / [SETUP:] the scene / A. label / A1. outcome / A2. outcome / B. ... / C. ... / CALLBACKS: ...
- The scene is the question page with the three labels; each label leads to its OWN pair of outcomes, which are
  weighted alternatives (a silent branch, one page each).  "SETUP:", "A." and "A1." are structural markers; the
  CALLBACKS line is a designer note.
- Weights (the V28 consequence rules, the lead's brief 2026-11-15): harmless common (20), a minor setback
  occasional (10: a small health loss, sickness, a small food loss), serious harm or a disappearance rare (5), a
  death -- and an amputation, which the owner allows only very rarely -- very rare (2).  Two outcomes of the same
  weight are equal (no weights written).

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

# Roles (the collection's ages; ELDER is its elder age, 55, as in V27 and the companion)
VILLAGER = {"kind": "villager", "min_age": 14}
GROWN = {"kind": "villager", "min_age": 18}
CHILD = {"kind": "villager", "min_age": 3, "max_age": 13}
YOUNG = {"kind": "villager", "min_age": 14, "max_age": 25}      # "a young weaver", "a young drummer"
YOUNGSTER = {"kind": "villager", "min_age": 3, "max_age": 17}   # "a young villager"
ELDER = {"kind": "villager", "min_age": 55}

MINOR, SERIOUS, BETTER = (-30, -10), (-60, -40), (10, 30)


def skilled(base: dict, skill: str) -> dict:
    return dict(base, skill={"names": [skill], "min": 1})


def sexed(base: dict, sex: str) -> dict:
    return dict(base, sex=sex)


# Effects --------------------------------------------------------------------------------------------------------------

def sk(role: str, skill: str, size: str = "small") -> dict:
    lo, hi = cc.SKILL_SIZES[size]
    return {"do": "skill", "role": role, "skills": [skill], "min": lo, "max": hi}


def health(role: str, rng: tuple[int, int]) -> dict:
    return {"do": "health_change", "role": role, "min": rng[0], "max": rng[1]}


def minor(role: str) -> dict:
    return health(role, MINOR)


def serious(role: str) -> dict:
    return health(role, SERIOUS)


def better(role: str) -> dict:
    """An outcome that says the patient recovers or improves."""
    return health(role, BETTER)


def ill(role: str) -> dict:
    return {"do": "sick", "role": role}


def die(role: str) -> dict:
    return {"do": "kill", "role": role, "cause": "unknown"}


def amputation(role: str) -> list[dict]:
    """The owner's lasting-injury toolkit (2026-11-15): health loss and a dislike of running; very rare."""
    return [serious(role), {"do": "preference", "role": role, "list": "dislikes", "preference": "running",
                            "very_rare": True}]


def food(size: str = "small", loss: bool = False) -> dict:
    e = {"do": "food", "size": size, "scaled": True}
    if loss:
        e["loss"] = True
    return e


def T(what: str, reason: str) -> dict:
    return {"what": what, "reason": reason}


def rarity_of(effects: list[dict]) -> str | None:
    """The outcome's weight class from its effects (module docstring)."""
    if any(e["do"] == "kill" or e.get("very_rare") for e in effects):
        return "very_rare"
    if any(e["do"] == "vanish" or (e["do"] == "health_change" and e["min"] <= SERIOUS[1]) for e in effects):
        return "rare"
    if any(e["do"] == "sick" or (e["do"] == "health_change" and e["max"] < 0) or (e["do"] == "food" and e.get("loss"))
           or (e["do"] == "skill" and e["max"] < 0) for e in effects):
        return "occasional"
    return None


# Source access --------------------------------------------------------------------------------------------------------

def rows(section: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    out = [r for r in data["rows"] if r.get("source") == lib.LIVING_ID and r["kind"] == "event"
           and r["section"] == section]
    return sorted(out, key=lambda r: r["lines"][0])


def num_of(row: dict) -> int:
    return int(re.match(r"lv[a-z]+?(\d+)_", row["id"]).group(1))


def line(n: int) -> str:
    with lib.use_source(lib.LIVING_ID):
        return lib.normalize_source_text(lib.line(n))


def shown(n: int) -> str:
    """Line n as a page shows it: typography and the structural markers applied."""
    with lib.use_source(lib.LIVING_ID):
        p = cc.processed_line(n, {}, {})
    return p[:1].upper() + p[1:]


def L(n: int) -> str:
    return f"L{n}"


def description_ok(text: str) -> bool:
    return bool(cc.DESCRIPTION_RE.fullmatch(text)) and len(text) <= cc.DESCRIPTION_MAX


def _clean(effects: list[dict], src: str) -> list[dict]:
    return [dict({k: v for k, v in e.items() if k != "very_rare"}, src=src) for e in effects]


def build(row: dict, roles: dict, desc: str | None, opts: dict) -> dict:
    """One event of the fixed shape (module docstring).  opts: fx {"a1": [effects]}, to {0 | "a1": [text_only]},
    games [..]."""
    h, last = row["lines"]
    assert last == h + 11 and line(last).startswith("CALLBACKS:"), row["id"]
    fx, to = opts.get("fx", {}), opts.get("to", {})
    unknown = (set(fx) | set(to)) - {0} - {f"{k}{i}" for k in "abc" for i in (1, 2)}
    assert not unknown, (row["id"], unknown)
    setup = h + 1
    if desc is None:
        desc = shown(setup)
    assert description_ok(desc), (row["id"], desc)
    nodes: dict = {}
    choices = []
    short = opts.get("label", {})
    for i, k in enumerate("abc"):
        lab = h + 2 + 3 * i
        assert line(lab).startswith(f"{k.upper()}. "), (row["id"], k)
        # A label too wide for a game's screen (vv_cie_graph label_max_px): its button shows the label's first
        # words (opts label {k: (text, lead)}); with lead True the whole sentence opens each of its outcome pages,
        # so every word is still shown.
        text, lead = short.get(k, (shown(lab), False))
        assert shown(lab).startswith(text), (row["id"], k, text)
        choices.append({"label": text, "next": k, "src": L(lab)})
        kids, pages = [], {}
        for j in (1, 2):
            o = lab + j
            assert line(o).strip().startswith(f"{k.upper()}{j}. "), (row["id"], k, j)
            key = f"{k}{j}"
            eff = fx.get(key, [])
            kid = {"next": key, "rarity": rarity_of(eff)}
            kids.append(kid)
            page = {"name": f"Outcome {key.upper()}", "text": shown(o), "src": L(o)}
            if lead:
                page.update(text=shown(lab) + "\n" + shown(o), src=f"{L(lab)},{L(o)}")
            if eff:
                page["effects"] = _clean(eff, L(o))
            if to.get(key):
                page["text_only"] = [dict(t, src=L(o)) for t in to[key]]
            pages[key] = page
        if any(kd["rarity"] for kd in kids) and kids[0]["rarity"] != kids[1]["rarity"]:
            for kd in kids:
                kd["weight"] = cc.RARITY_WEIGHTS[kd["rarity"]]
                if not kd["rarity"]:
                    del kd["rarity"]
        else:
            for kd in kids:
                kd.pop("rarity")
        nodes[k] = {"type": "branch", "name": f"Answer {k.upper()}", "children": kids}
        nodes.update(pages)
    q = {"type": "question", "name": "The setup", "text": shown(setup), "src": L(setup), "choices": choices}
    if to.get(0):
        q["text_only"] = [dict(t, src=L(setup)) for t in to[0]]
    nodes = {"setup": q, **nodes}
    used = {e["role"] for n in nodes.values() for e in n.get("effects", []) if e.get("role")}
    col = {"id": row["id"], "title_src": L(h),
           "ledger": [{"src": L(last), "kind": "note", "why": "CALLBACKS: the designer's callback tags, never shown"}],
           "description": desc}
    cast_only = [r for r in roles if r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": row["games"],
            "collection": col, "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "setup",
            "nodes": nodes}


def write_and_check(docs: list[tuple[str, str, dict]]) -> int:
    paths = []
    for section, eid, doc in docs:
        p = lib.LIVING_DIR / section / f"{eid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
