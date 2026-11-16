"""The owner's GO files (scripts/go_events/gen_go.py): the manifest's rows, the files written, the pieces input."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_lib as lib  # noqa: E402

LEFT_OUT = {"s027_isolan_fire", "s070_isolan_healer"}      # they cast an Isolan (gen_go.LeftOut)


def _rows():
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return [r for r in data["rows"] if r.get("source") in lib.GO_SOURCES and r["kind"] == "event"]


def test_sources_are_frozen():
    for sid in lib.GO_SOURCES:
        assert lib.source_sha256(sid) == lib.recorded_sha256(sid)


def test_every_event_has_a_row_and_a_file():
    rows = _rows()
    assert len(rows) == 675
    files = {p.stem for sid in lib.GO_SOURCES for p in (lib.COLLECTION_DIR / sid).glob("*/*.json")}
    assert files == {r["id"] for r in rows} - LEFT_OUT
    assert all(len(r["id"]) <= 22 for r in rows)


def test_credits():
    by = {r["id"][:4]: r["credit"]["text"] for r in _rows()}
    assert by["s001"] == "Written by Lorsieab2."
    assert by["s021"].startswith("Created by Lorsieab2; drafted with ChatGPT")
    assert by["b001"].startswith("Written by Claude to Lorsieab2's style guide")


def test_equal_chances_and_seed_pieces():
    doc = json.loads((lib.COLLECTION_DIR / "balance" / "bal" / "b001_undertow.json").read_text(encoding="utf-8"))
    kids = doc["nodes"]["c1"]["children"]
    assert len({k.get("weight", 1) for k in kids}) == 1
    pieces = json.loads((ROOT / "data" / "procedural_pieces" / "go_seeds.json").read_text(encoding="utf-8"))
    assert any(p["event"] == "b001_undertow" and p["kind"] == 1 for p in pieces["pieces"])
