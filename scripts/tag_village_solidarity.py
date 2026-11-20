"""Write data/event_collection/solidarity_tags.json: the Village Solidarity tags of the collection's events.

The owner (2026-11-17): "tag existing new events where their text clearly carries a listed feeling".  Rules (kept
deliberately strict, so a tag is only where the words say it):

  * PAGES: only an event's ENDINGS (a popup page with no next page) are tagged, as an outcome carries the tag.  An
    ending whose own text (its text and every variant) carries only RAISE words is "raise", only LOWER words
    "lower", only the quiet words (solemn remembrance, quiet reflection, bittersweet) "neutral"
    (src/vv_village_scores.py tag_for_text); mixed or none: untagged.
  * KIND (the collection draw's odds): an event whose title and Pick Island Event sentence name a celebration,
    song, gathering, feast or festival is "cooperative"; one that names an apology, making peace, forgiveness or
    patching up a quarrel is "repair"; both or neither: none.

The event files themselves (the owner's approved text) are never changed: the build applies this file
(scripts/build_event_collection_features.py apply_solidarity_tags).  Run, then rebuild the collection rows.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cie  # noqa: E402
import vv_village_scores as scores  # noqa: E402
import build_event_collection_features as coll  # noqa: E402
from collection_check import graph_for_engine  # noqa: E402

COOPERATIVE = re.compile(r"(?<![a-z])(celebrat\w*|festival|feast\w*|song|songs|sing|sang|singing|gathering|dance|"
                         r"dancing|work together|worked together)(?![a-z])", re.I)
REPAIR = re.compile(r"(?<![a-z])(apolog\w*|sorry|make peace|made peace|making peace|truce|forgiv\w*|forgave|"
                    r"reconcil\w*|make amends|making amends|patch things up)(?![a-z])", re.I)


def event_kind(title: str, description: str) -> str:
    text = f"{title} {description}"
    co, re_ = bool(COOPERATIVE.search(text)), bool(REPAIR.search(text))
    return "cooperative" if co and not re_ else "repair" if re_ and not co else ""


def endings(g: dict) -> list[str]:
    return [nid for nid, n in g["nodes"].items()
            if n["type"] == "popup" and not n["children"] and not n["choices"] and not n["else"]]


def page_tag(node: dict) -> str | None:
    texts = [node["text"]] + [v["text"] for v in node.get("variants", [])]
    tags = {scores.tag_for_text(t) for t in texts if t.strip()}
    if len(tags) == 1:
        return next(iter(tags))
    return None                                    # variants disagree, or nothing clear


def main() -> None:
    pools = coll.shared_pools()
    out: dict[str, dict] = {}
    counts = {"raise": 0, "lower": 0, "neutral": 0, "cooperative": 0, "repair": 0, "events": 0}
    for path in coll.event_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vvfp-cie-graph" or not isinstance(data.get("collection"), dict):
            continue
        g, problems = cie.validate(graph_for_engine(data), scrolling=True, shared_pools=pools)
        if problems:
            continue
        ident = str(data["collection"].get("id", ""))
        nodes = {}
        for nid in endings(g):
            tag = page_tag(g["nodes"][nid])
            if tag:
                nodes[nid] = tag
                counts[tag] += 1
        kind = event_kind(str(g.get("title", "")), str(data["collection"].get("description", "")))
        if kind:
            counts[kind] += 1
        if nodes or kind:
            out[ident] = {**({"kind": kind} if kind else {}), **({"nodes": dict(sorted(nodes.items()))} if nodes else {})}
            counts["events"] += 1
    coll.SOLIDARITY_TAGS.write_text(json.dumps(dict(sorted(out.items())), indent=1) + "\n", encoding="utf-8",
                                    newline="\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
