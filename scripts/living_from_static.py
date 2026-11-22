"""Mixer versions of every static collection event (the owner, 2026-11-15: "make mixer versions of every event too in
addition to static ones").

Each static event (data/event_collection, every source) becomes a Living Event Engine seed of bank 2 ("static") with
up to three versions (k = 0, 1, 2), packed with the other living seeds (docs/event-collection/living-pack.md).  The
static event itself never changes.  A version is the event's own compiled graph with:

* its choices in another order on every question page (each choice keeps its own follow-ups and codas: only the
  order of the buttons changes), and
* on about one version in three, where it fits, the Living Engine's personality frame after the first page: "(A),
  {a humble villager}, and (B), {a curious villager}, disagree about what should happen next. Their status alone
  does not settle the matter." (the frame's own words, vv_living_mixer.FRAME_TAIL; A and B the two cast villagers
  its first page names; personalities the bank's, never one with a risk tag; B's never the same as A's).

The frame fits only where two cast villagers can disagree: at least two villager roles (not a special one), and
never a catalogue or study entry, a nature report, or a grief, loss, illness or death scene.  Casting is the
engine's at run time (every version recasts), so the event's roles, ages, games, patches, Guardians wording and
gates are the static event's own.  An event with no choices to reorder and no page the strict frame fits gets its
versions from quiet_versions (the owner, 2026-11-16): one of its random outcomes left out (a different one each
version, where a random page has three or more), the frame where it casts two villagers, else one version that only
recasts; only a version that fails validation is ever dropped (static_only, with the reason).

Each source is one series, `living_st_<source>`: the draw counts a series as one event, so the mixer versions never
swamp the static events.  Mixer versions have no outcome records (living-pack.md 2.4: count 0).

Every version carries its static event's content controls (src/vv_event_content.py, with_content): the same
"Content note: ..." first line, the same content filters dropping the same outcomes and the same story traits, from
the static event's source's tag table (the nodes the version still has).

    python scripts/living_from_static.py            # print the counts (writes nothing)

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import vv_cie_graph as cg  # noqa: E402
import vv_living_mixer as mx  # noqa: E402

VERSIONS = 3
BANK_STATIC = 2
ID_PREFIX = "living_st_"
NO_FRAME_SECTIONS = {"cat", "an_fauna", "dr_nat"}          # catalogue / study entries, nature reports
SERIOUS = re.compile(r"\b(griev\w*|grief|mourn\w*|funeral|bereav\w*|dies|died|death|dead|dying|illness|ill|sick\w*|"
                     r"injur\w*|wound\w*|trauma\w*|loss|lost (?:a|her|his|their) (?:child|baby|partner)|grave|"
                     r"miscarr\w*|stillborn|pregnan\w*)\b", re.I)
ORDERED_LABEL = re.compile(r"^\s*(?:[A-Ea-e1-9][.):]|first\b|second\b|third\b|option [a-e1-9]\b)", re.I)
POOL_A, POOL_B = "LVPA", "LVPB"


def _rng(key: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "little"))


def seed_id(event_id: str) -> str:
    return ID_PREFIX + hashlib.sha1(event_id.encode("utf-8")).hexdigest()[:6]


def series_of(source: str) -> str:
    return (ID_PREFIX + re.sub(r"[^a-z0-9_]", "_", source.lower()))[:24]


def personalities(bank: mx.Bank) -> list[str]:
    return [f"{p['article']} {p['text']} villager" for p in bank.pers if not p["tags"]]


def _texts(g: dict) -> str:
    out = [g.get("title", "")]
    for n in g["nodes"].values():
        out.append(n.get("text") or "")
        out += [v.get("text") or "" for v in n.get("variants") or []]
        out += [c.get("label") or "" for c in n.get("choices") or []]
    for p in (g.get("pools") or {}).values():
        out += [it["text"] if isinstance(it, dict) else str(it) for it in p.get("items", [])]
    return "\n".join(out)


def _first_page(g: dict) -> str | None:
    """The first node with text on the start's path (the setup the frame follows)."""
    nid, seen = g["start"], set()
    while nid and nid not in seen:
        seen.add(nid)
        n = g["nodes"][nid]
        if n.get("text"):
            return nid
        kids = n.get("children") or []
        nid = kids[0]["next"] if len(kids) == 1 else None
    return None


def frame_roles(g: dict) -> list[str]:
    """The two villagers the frame names: the first two cast (not special) villagers the first page itself names, in
    the order it names them (the frame only follows a page that is about them)."""
    nid = _first_page(g)
    text = (g["nodes"][nid].get("text") or "") if nid else ""
    found = []
    for m in re.finditer(r"\(([A-Za-z][A-Za-z0-9_]*)(?:\.[^()]*)?\)", text):
        rid = m.group(1)[:1].lower() + m.group(1)[1:]
        rid = next((r for r in g["roles"] if r.lower() == rid.lower()), None)
        r = g["roles"].get(rid) if rid else None
        if r and r.get("kind") == "villager" and not r.get("special") and rid not in found:
            found.append(rid)
    return found[:2]


def frame_fits(e: dict, g: dict) -> tuple[bool, str]:
    if e.get("section") in NO_FRAME_SECTIONS:
        return False, "a catalogue, study or nature entry"
    if len(frame_roles(g)) < 2:
        return False, "its first page names fewer than two cast villagers"
    if SERIOUS.search(_texts(g)):
        return False, "a grief, loss, illness or death scene"
    if _first_page(g) is None:
        return False, "no first page"
    if any(name in (g.get("pools") or {}) for name in (POOL_A, POOL_B)):
        return False, "pool names taken"
    return True, ""


def reorderable(g: dict) -> list[str]:
    """The question pages whose buttons may change order (two or more, none of them numbered or ordinal)."""
    out = []
    for nid, n in g["nodes"].items():
        ch = n.get("choices") or []
        if n.get("type") == "question" and len(ch) >= 2 and not any(ORDERED_LABEL.match(c.get("label") or "")
                                                                    for c in ch):
            out.append(nid)
    return out


def _orders(g: dict, qs: list[str], rng: random.Random, want: int) -> list[dict[str, tuple[int, ...]]]:
    """Up to `want` different choice orders (never the static order), one permutation per question page."""
    found: list[dict[str, tuple[int, ...]]] = []
    if not qs:
        return found
    seen = {tuple(tuple(range(len(g["nodes"][q]["choices"]))) for q in qs)}
    for _ in range(50 * want):
        o = {}
        for q in qs:
            idx = list(range(len(g["nodes"][q]["choices"])))
            rng.shuffle(idx)
            o[q] = tuple(idx)
        key = tuple(o[q] for q in qs)
        if key not in seen:
            seen.add(key)
            found.append(o)
            if len(found) == want:
                break
    return found


def _with_frame(g: dict, pers: list[str], roles: list[str] | None = None) -> dict:
    a, b = roles or frame_roles(g)
    nid = _first_page(g)
    n = g["nodes"][nid]
    cap = lambda r: r[:1].upper() + r[1:]  # noqa: E731
    frame = f"({cap(a)}), {{{POOL_A}}}, and ({b}), {{{POOL_B}}}, {mx.FRAME_TAIL}"
    n["text"] = n["text"].rstrip() + "\n" + frame
    g.setdefault("pools", {})
    g["pools"][POOL_A] = {"items": [{"text": t, "weight": 1, "if": None} for t in pers], "distinct": False}
    g["pools"][POOL_B] = {"items": [{"text": t, "weight": 1, "if": None} for t in pers], "distinct": False,
                          "distinct_from": [POOL_A]}
    return g


def _apply_order(g: dict, order: dict[str, tuple[int, ...]]) -> dict:
    for q, idx in order.items():
        ch = g["nodes"][q]["choices"]
        g["nodes"][q]["choices"] = [ch[i] for i in idx]
    return g


def mood_of(g: dict) -> int:
    return 2 if SERIOUS.search(_texts(g)) else 1


def versions(e: dict, bank: mx.Bank, pers: list[str]) -> tuple[list[dict], str]:
    """(the versions' graph dicts with their plan, why none) for one compiled static event."""
    g0 = e["graph"]
    rng = _rng(e["id"])
    fits, why_not = frame_fits(e, g0)
    qs = reorderable(g0)
    frame_k = rng.randrange(VERSIONS) if fits else None
    orders = _orders(g0, qs, rng, VERSIONS)
    out = []
    for k in range(VERSIONS):
        frame = k == frame_k
        order = orders[k] if k < len(orders) else None
        if order is None and not frame:
            continue
        g = copy.deepcopy(e["graph"])
        if order:
            _apply_order(g, order)
        if frame:
            _with_frame(g, pers)
        out.append({"k": len(out), "graph": g, "frame": frame, "order": order})
    if not out:
        out = quiet_versions(e, g0, rng, pers)        # the owner, 2026-11-16: these events get versions too
    if not out:
        return [], ("no choices to reorder and " + (why_not or "no frame"))
    return out, ""


def _reach(g: dict) -> set[str]:
    seen, todo = set(), [g["start"]]
    while todo:
        nid = todo.pop()
        if nid in seen or nid not in g["nodes"]:
            continue
        seen.add(nid)
        n = g["nodes"][nid]
        for c in (n.get("children") or []) + (n.get("choices") or []):
            todo += [x for x in (c.get("next"), c.get("else")) if x]
        if n.get("else"):
            todo.append(n["else"])
    return seen


def _without_child(g: dict, nid: str, i: int) -> dict:
    """g with child i of random node nid left out, and the nodes no path reaches any more."""
    g = copy.deepcopy(g)
    kids = g["nodes"][nid]["children"]
    g["nodes"][nid]["children"] = kids[:i] + kids[i + 1:]
    keep = _reach(g)
    g["nodes"] = {k: v for k, v in g["nodes"].items() if k in keep}
    return g


def quiet_versions(e: dict, g0: dict, rng: random.Random, pers: list[str]) -> list[dict]:
    """An event with no choices to reorder and no page the strict frame fits (the owner, 2026-11-16): up to three
    versions that recast its villagers and vary which of its random outcomes can come (one left out of a random page
    of three or more, a different one each version), with the personality frame on about one in three where the
    event casts two villagers (not a catalogue, nature, grief, loss, illness or death scene); else one version that
    only recasts.  The owner's words are never changed."""
    branches = [nid for nid, n in g0["nodes"].items() if n.get("type") == "branch"
                and len(n.get("children") or []) >= 3 and not any(c.get("if") or c.get("else") for c in n["children"])]
    two = [rid for rid, r in g0["roles"].items() if r.get("kind") == "villager" and not r.get("special")][:2]
    loose_fit = len(two) == 2 and e.get("section") not in NO_FRAME_SECTIONS and not SERIOUS.search(_texts(g0)) \
        and _first_page(g0) is not None and not any(nm in (g0.get("pools") or {}) for nm in (POOL_A, POOL_B))
    plans: list[tuple[int | None, bool]] = []
    if branches:
        n = len(g0["nodes"][branches[0]]["children"])
        drops = list(range(n))
        rng.shuffle(drops)
        plans = [(d, False) for d in drops[:VERSIONS]]
    if loose_fit:
        if plans:
            k = rng.randrange(len(plans))
            plans[k] = (plans[k][0], True)
        else:
            plans = [(None, True)]
    if not plans:
        plans = [(None, False)]                       # recast only
    out = []
    for drop, frame in plans:
        g = _without_child(g0, branches[0], drop) if drop is not None else copy.deepcopy(g0)
        if frame:
            _with_frame(g, pers, two)
        out.append({"k": len(out), "graph": g, "frame": frame, "order": None, "drop": drop})
    return out


def with_content(e: dict, g: dict) -> dict:
    """Version graph `g` (validated) of static event `e` with the content controls written in
    (src/vv_event_content.py inject): the static event's source's tag table, the same as its own .cieg."""
    import vv_event_content as content
    source = e.get("source", "v28")
    return content.inject(g, content.node_tags_for(source, e["id"], g), content.extras_for(source, e["id"], g))[0]


def build(events: list[dict], bank: mx.Bank | None = None) -> tuple[list[mx.Variant], dict[str, str]]:
    """Every static event's mixer versions as mixer Variants (validated and compiled), and the static-only events
    {id: reason}."""
    bank = bank or mx.Bank()
    pers = personalities(bank)
    variants: list[mx.Variant] = []
    static_only: dict[str, str] = {}
    ids: dict[str, str] = {}
    index_in_series: dict[str, int] = {}
    for e in sorted(events, key=lambda x: x["id"]):
        vs, why = versions(e, bank, pers)
        if not vs:
            static_only[e["id"]] = why
            continue
        sid = seed_id(e["id"])
        if sid in ids:
            raise SystemExit(f"living_from_static: {e['id']} and {ids[sid]} share the seed id {sid}")
        ids[sid] = e["id"]
        series = series_of(e.get("source", "v28"))
        si = index_in_series.get(series, 0)
        index_in_series[series] = si + 1
        for v in vs:
            g, problems = cg.validate(v["graph"], scrolling=True)
            if problems:
                if v["frame"] or v.get("drop") is not None:
                    continue          # the frame does not fit this page, or the outcome left out is one a later
                    #                   page asks about ("visited"): this version is left out
                raise SystemExit(f"living_from_static: {e['id']} k={v['k']}: " + "; ".join(problems[:4]))
            # The content controls, as the static event's own compiled file has them (build_event_collection_features
            # compile_events): its source's node tags (the nodes this version still has), so the version shows the
            # same "Content note: ..." line and the same content filters drop the same outcomes (R6, 2026-11-21:
            # every mixer version had lost its note).
            g = with_content(e, g)
            var = mx.Variant(seed=e["id"], manifest_id=sid, series=series, bank=BANK_STATIC, cat_index=0,
                             seed_index=si, k=v["k"], games=list(e["games"]), flags=0, graph=g, outcomes=[],
                             plan={"static": e, "frame": v["frame"], "order": v["order"], "node_index": {}},
                             mood=mood_of(g))
            var.cieg = cg.compile_graph(g)
            variants.append(var)
        if not variants or variants[-1].seed != e["id"]:
            static_only[e["id"]] = "its only version (the frame) does not fit the page"
    return variants, static_only


STATIC_ONLY_DOC = ROOT / "docs" / "event-collection" / "living-from-static.md"


def write_static_only_doc(events: list[dict], variants: list[mx.Variant], static_only: dict[str, str]) -> None:
    """docs/event-collection/living-from-static.md: the counts per series and every static-only event with its reason."""
    title = {e["id"]: e["title"] for e in events}
    src = {e["id"]: e.get("source", "v28") for e in events}
    seeds: dict[str, set] = {}
    vers: dict[str, int] = {}
    frames: dict[str, int] = {}
    for v in variants:
        seeds.setdefault(v.series, set()).add(v.manifest_id)
        vers[v.series] = vers.get(v.series, 0) + 1
        frames[v.series] = frames.get(v.series, 0) + (1 if v.plan["frame"] else 0)
    lines = ["# Mixer versions of the static events (scripts/living_from_static.py)", "",
             "The owner, 2026-11-15: every static event also has mixer versions (living-pack.md 1), up to three each: "
             "its choices in other orders, and on one of them, where it fits, the personality frame. Generated by "
             "`scripts/build_event_collection_features.py`; do not edit.", "",
             f"Static events {len(events)}; with mixer versions {sum(len(s) for s in seeds.values())} "
             f"({len(variants)} versions, {sum(frames.values())} with the frame); static only {len(static_only)}.", "",
             "| Series | Events | Versions | With the frame |", "|---|---|---|---|"]
    for s in sorted(seeds):
        lines.append(f"| `{s}` | {len(seeds[s])} | {vers[s]} | {frames[s]} |")
    lines += ["", "## Static only (nothing to mix)", "",
              "An event is static only when none of its versions validates.", "",
              "| Event | Source | Title | Why |", "|---|---|---|---|"]
    for eid in sorted(static_only):
        lines.append(f"| `{eid}` | {src.get(eid, '')} | {title.get(eid, '').replace('|', '/')} | {static_only[eid]} |")
    STATIC_ONLY_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    import build_event_collection_features as bf
    events = bf.compile_events()
    variants, static_only = build(events)
    seeds = {v.manifest_id for v in variants}
    frames = sum(1 for v in variants if v.plan["frame"])
    by_series: dict[str, set] = {}
    for v in variants:
        by_series.setdefault(v.series, set()).add(v.manifest_id)
    print(f"{len(events)} static events: {len(seeds)} seeds, {len(variants)} versions ({frames} with the frame), "
          f"{len(by_series)} series; static only {len(static_only)}")
    for s in sorted(by_series):
        print(f"  {s}: {len(by_series[s])}")
    for eid, why in sorted(static_only.items()):
        print(f"  static only: {eid}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
