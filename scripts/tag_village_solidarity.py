"""Write data/event_collection/solidarity_tags.json: the Village Solidarity tags of the collection's events, and
data/living_events/solidarity_tags.json: the Living Event Engine's (its outcome archetypes and MC outcomes).

The owner (2026-11-17): "tag existing new events where their text clearly carries a listed feeling"; and
(2026-11-20): "add tags to every single event!!!" -- EVERY ending of every added event carries a tag now, read from
its text AND its effects by the owner's rule (src/vv_solidarity_endings.py: raise good for the whole village, lower
bad for it, neutral one villager's own change, mixed results, nothing, or story only).

  * PAGES: an event's ENDINGS (a popup page with nowhere to go; the outcome-effects pass's X__fx / X__text pair
    as their X), each tagged, in this order:
      1. the reviewed judgement calls, data/event_collection/solidarity_review.json ({event: {node: [tag, why]}});
      2. the draft's own tag (Living Culture, LCA..LCJ: its "[Solidarity: ...]" ledger note);
      3. the 2026-11-17 word rule (only RAISE, only LOWER or only quiet words: src/vv_village_scores.py
         tag_for_text), unless the ending's effects lower the village (a death, a disappearance, a lost baby, a
         Heathen, damaged huts, a sickness): then rule 4;
      4. src/vv_solidarity_endings.py classify (the effects first, then the words).
  * KIND (the collection draw's odds): an event whose title and Pick Island Event sentence name a celebration,
    song, gathering, feast or festival is "cooperative"; one that names an apology, making peace, forgiveness or
    patching up a quarrel is "repair"; both or neither: none.

The event files themselves (the owner's approved text) are never changed: the build applies this file
(scripts/build_event_collection_features.py apply_solidarity_tags).  Run, then rebuild the collection rows.

    python scripts/tag_village_solidarity.py [--table OUT.txt]    # OUT.txt: every ending, its tag and why
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cie  # noqa: E402
import vv_village_scores as scores  # noqa: E402
import vv_solidarity_endings as se  # noqa: E402
import build_event_collection_features as coll  # noqa: E402
from collection_check import graph_for_engine  # noqa: E402

REVIEW = coll.DATA / "solidarity_review.json"
LIVING_TAGS = ROOT / "data" / "living_events" / "solidarity_tags.json"
LEDGER_TAG = re.compile(r"^\[Solidarity: (raise|lower|neutral)\]$")

COOPERATIVE = re.compile(r"(?<![a-z])(celebrat\w*|festival|feast\w*|song|songs|sing|sang|singing|gathering|dance|"
                         r"dancing|work together|worked together)(?![a-z])", re.I)
REPAIR = re.compile(r"(?<![a-z])(apolog\w*|sorry|make peace|made peace|making peace|truce|forgiv\w*|forgave|"
                    r"reconcil\w*|make amends|making amends|patch things up)(?![a-z])", re.I)


def event_kind(title: str, description: str) -> str:
    text = f"{title} {description}"
    co, re_ = bool(COOPERATIVE.search(text)), bool(REPAIR.search(text))
    return "cooperative" if co and not re_ else "repair" if re_ and not co else ""


def word_tag(g: dict, pages: list[str]) -> str | None:
    """The 2026-11-17 rule: the tag every text of the ending's pages (and their variants) clearly carries."""
    texts = [t for p in pages for t in [g["nodes"][p]["text"]] + [v["text"] for v in g["nodes"][p].get("variants", [])]]
    tags = {scores.tag_for_text(t) for t in texts if t.strip()}
    return next(iter(tags)) if len(tags) == 1 and None not in tags else None


def ledger_tags(data: dict) -> dict[str, str]:
    """The draft's own ending tags: its "[Solidarity: ...]" ledger notes, on the node of the same source line."""
    by_src: dict[str, list[str]] = {}
    for nid, n in data.get("nodes", {}).items():
        if n.get("src"):
            by_src.setdefault(n["src"], []).append(nid)
    out = {}
    for item in (data.get("collection") or {}).get("ledger", []):
        m = LEDGER_TAG.match(str(item.get("text", "")))
        if m:
            for nid in by_src.get(item.get("src"), []):
                out[nid] = m.group(1)
    return out


def ending_tag(g: dict, key: str, pages: list[str], review: dict, ledger: dict) -> tuple[str, str]:
    """(tag, why) of one ending, by the rules above."""
    if key in review:
        return review[key][0], review[key][1]
    if key in ledger:
        return ledger[key], "the draft's own tag"
    text, effects = se.ending_reading(g, key, pages)
    old = word_tag(g, pages)
    strong, _good, _bad = se.effect_signals(effects)
    if old and not (strong and old != "lower"):
        return old, "its words (the 2026-11-17 rule)"
    tag, why, _sure = se.classify(text, effects)
    return tag, why


def collection_tags(review: dict | None = None) -> tuple[dict, list[tuple]]:
    """({event id: {"kind"?, "nodes"}}, [(group, event id, node, tag, why)]) of every collection event."""
    review = json.loads(REVIEW.read_text(encoding="utf-8")) if review is None and REVIEW.is_file() else (review or {})
    pools = coll.shared_pools()
    out: dict[str, dict] = {}
    rows: list[tuple] = []
    for path in coll.event_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vvfp-cie-graph" or not isinstance(data.get("collection"), dict):
            continue
        g, problems = cie.validate(graph_for_engine(data), scrolling=True, shared_pools=pools)
        if problems:
            raise SystemExit(f"{path.relative_to(ROOT)}: " + "; ".join(problems[:3]))
        ident = str(data["collection"].get("id", ""))
        group = path.relative_to(coll.DATA).parts[0]
        nodes = {}
        led = ledger_tags(data)
        for key, pages in sorted(se.endings(g).items()):
            tag, why = ending_tag(g, key, pages, review.get(ident, {}), led)
            nodes[key] = tag
            rows.append((group, ident, key, tag, why))
        kind = event_kind(str(g.get("title", "")), str(data["collection"].get("description", "")))
        out[ident] = {**({"kind": kind} if kind else {}), "nodes": nodes}
    return dict(sorted(out.items())), rows


def living_tags() -> tuple[dict, list[tuple]]:
    """The Living Event Engine's endings: each outcome archetype (an LE variant's ending is one) and each MC outcome,
    by the same rule (src/vv_solidarity_endings.py classify, with the reviewed calls)."""
    import vv_living_mixer as lm
    review = json.loads(REVIEW.read_text(encoding="utf-8")).get("living_bank", {}) if REVIEW.is_file() else {}
    bank = lm.Bank()
    out, rows = {}, []
    for a in bank.archetypes:
        if a["id"] in review:
            tag, why = review[a["id"]]
        else:
            tag, why, _ = se.classify(lm.plain(a["text"]), a["effects"])
        out[a["id"]] = tag
        rows.append(("living_engine", a["id"], "archetype", tag, why))
    for sit in bank.mc_sits:
        for ap in sit["approaches"]:
            for o in ap["outcomes"]:
                if o["id"] in review:
                    tag, why = review[o["id"]]
                else:
                    tag, why, _ = se.classify(lm.plain(o["text"]), o["effects"])
                out[o["id"]] = tag
                rows.append(("living_mc", sit["id"], o["id"], tag, why))
    return dict(sorted(out.items())), rows


def write_compact(path: Path, table: dict) -> None:
    """One entry per line (a diff shows each event's change on its own line)."""
    lines = [f" {json.dumps(k)}: {json.dumps(v, sort_keys=True)}" for k, v in table.items()]
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8", newline="\n")


def table_text(rows: list[tuple]) -> str:
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for group, _i, _n, tag, _w in rows:
        counts[group][tag] += 1
        counts["ALL"][tag] += 1
    out = ["Village Solidarity: every added event's ending, its tag and why (scripts/tag_village_solidarity.py)", "",
           "Counts per group (raise / lower / neutral):"]
    for group in sorted(counts, key=lambda g: (g == "ALL", g)):
        c = counts[group]
        out.append(f"  {group:16} raise {c['raise']:5}  lower {c['lower']:5}  neutral {c['neutral']:5}  "
                   f"total {sum(c.values()):5}")
    out += ["", "event id | ending | tag | short reason"]
    out += [f"{i} | {n} | {t} | {w}" for _g, i, n, t, w in rows]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    table, rows = collection_tags()
    write_compact(coll.SOLIDARITY_TAGS, table)
    living, lrows = living_tags()
    write_compact(LIVING_TAGS, living)
    rows += lrows
    if "--table" in argv:
        out = Path(argv[argv.index("--table") + 1])
        out.write_text(table_text(rows), encoding="utf-8")
    counts = collections.Counter(r[3] for r in rows)
    print(json.dumps({"endings": len(rows), **counts,
                      "cooperative": sum(1 for v in table.values() if v.get("kind") == "cooperative"),
                      "repair": sum(1 for v in table.values() if v.get("kind") == "repair")}))


if __name__ == "__main__":
    main()
