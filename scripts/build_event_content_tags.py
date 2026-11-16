"""Write the content tag tables of the new island events: data/event_collection/content_tags/<source>.json, one per
source (v28, companion, living, horizon, rolemodels, and every later source), so the event files are never churned.

Each event's nodes are tagged with the content filters F01-F28 (src/vv_event_content.py: tag_graph -- the effects
that always carry a filter, such as a death, a disappearance or a lost pregnancy, and a careful pass over every node's
words), then each source's writers' tags are added where its build reports give them (WRITER_TAGS below).  The
Living Event Engine's archetypes (the mixer's outcome_categories) go in living_engine.json.

    python scripts/build_event_content_tags.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import vv_cie_graph as cie  # noqa: E402
import vv_event_content as content  # noqa: E402
import vv_living_mixer as living  # noqa: E402
from build_event_collection_features import DATA, event_files, shared_pools  # noqa: E402
from collection_check import graph_for_engine  # noqa: E402

# The writers' own tags, by source, event and node (from the build reports); added to what tag_graph finds.
WRITER_TAGS: dict[str, dict[str, dict[str, list[str]]]] = {}


def build() -> dict[str, dict]:
    pools = shared_pools()
    tables: dict[str, dict] = {}
    for path in event_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vvfp-cie-graph" or not isinstance(data.get("collection"), dict):
            continue
        g, problems = cie.validate(graph_for_engine(data), scrolling=True, shared_pools=pools)
        if problems:
            raise SystemExit(f"{path}: " + "; ".join(problems[:3]))
        meta = data["collection"]
        source, ident = meta.get("source", "v28"), meta["id"]
        tags = {n: set(t) for n, t in content.tag_graph(g).items()}
        for node, extra in WRITER_TAGS.get(source, {}).get(ident, {}).items():
            tags.setdefault(node, set()).update(extra)
        tables.setdefault(source, {})[ident] = content.table_entry(g, {n: sorted(t) for n, t in tags.items() if t})
    return tables


def write(tables: dict[str, dict]) -> None:
    content.TAGS_DIR.mkdir(parents=True, exist_ok=True)
    for source, events in sorted(tables.items()):
        body = {"format": "vvfp-event-content-tags", "version": 1, "source": source,
                "filters": content.FILTERS, "events": dict(sorted(events.items()))}
        content.table_path(source).write_text(json.dumps(body, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        tagged = sum(1 for e in events.values() if e["filters"])
        print(f"{source}: {len(events)} events, {tagged} with content tags")
    arcs = {a: {"index": c["index"], "filters": c["filters"]} for a, c in living.outcome_categories().items()}
    body = {"format": "vvfp-event-content-tags", "version": 1, "source": "living_engine",
            "note": "the Living Event Engine's archetypes (vv_living_mixer.outcome_categories); each variant's own "
                    "words and effects are tagged when the mixer compiles it (vv_living_mixer.variant_tags)",
            "archetypes": arcs}
    (content.TAGS_DIR / "living_engine.json").write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write(build())
