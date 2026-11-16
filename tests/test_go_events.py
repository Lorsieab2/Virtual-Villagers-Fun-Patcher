"""The owner's GO files (scripts/go_events/gen_go.py): the manifest's rows, the files written, the pieces input."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_lib as lib  # noqa: E402

LEFT_OUT: set[str] = set()      # S027 and S070 cast their Isolan as a heathen_ok role (the owner, 2026-11-16)


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


def test_mixer_only_event_is_in_no_manifest():
    import build_event_collection_features as b
    ev = {"id": "x", "games": [1], "mixer_only": True}          # never read further: it is skipped
    assert b.manifest_text(1, [ev]).count("\n") == 2


def test_isolan_roles_are_heathen_ok():
    import collection_check as cc
    for stem in ("s027_isolan_fire", "s070_isolan_healer"):
        path = lib.COLLECTION_DIR / "rewrites" / "rw_s" / f"{stem}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["roles"]["subject"]["heathen_ok"] is True
        assert "heathen_ok" not in cc.graph_for_engine(doc)["roles"]["subject"]   # the engine flag is pending
        rep = cc.Report("x")
        cc.check_safety(doc, rep)
        assert not rep.problems
        # a Heathen may never be killed: the same role with a kill is refused
        bad = json.loads(json.dumps(doc))
        bad["nodes"]["c1o1"].setdefault("effects", []).append({"do": "kill", "role": "subject", "cause": "unknown"})
        rep = cc.Report("x")
        cc.check_safety(bad, rep)
        assert any("kill may never reach a Heathen" in p for p in rep.problems)


MIE_IDS = {"mie_adventurer", "mie_cave_explorers", "mie_climb", "mie_troubling_signs", "mie_diving",
           "mie_mysterious_mask", "mie_dolphins", "mie_remembrance", "mie_rumblings"}


def test_more_island_events_are_mixer_only():
    assert lib.source_sha256(lib.MIE_ID) == lib.recorded_sha256(lib.MIE_ID)
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    rows = {r["id"] for r in data["rows"] if r.get("source") == lib.MIE_ID and r["kind"] == "event"}
    assert rows == MIE_IDS
    assert data[lib.MIE_ID]["uncovered_lines"] == [] and data[lib.MIE_ID]["overlaps"] == []
    files = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in lib.MIE_DIR.glob("*/*.json")}
    assert set(files) == MIE_IDS
    assert all(d["collection"]["mixer_only"] is True for d in files.values())
    # never in a shipped manifest: the originals run from "VVFP More Island Events.dll"
    for g in range(1, 6):
        for m in (ROOT / "assets" / "event_collection" / f"vv{g}").glob("manifest-*.txt"):
            ids = {ln.split("\t")[0] for ln in m.read_text(encoding="utf-8").splitlines() if ln and ln[0] != "#"}
            assert not ids & MIE_IDS, m.name


def test_more_island_events_odds():
    adv = json.loads((lib.MIE_DIR / "mie" / "mie_adventurer.json").read_text(encoding="utf-8"))
    finds = [k["next"] for k in adv["nodes"]["a_open"]["children"]]
    assert finds.count("find_dirt") == 2 and finds.count("find_meat") == 1      # 50 / 25 / 25
    home = [k["next"] for k in adv["nodes"]["b_open"]["children"]]
    assert home.count("b_home") == 9 and home.count("b_lost") == 1               # 90 / 10
    cave = json.loads((lib.MIE_DIR / "mie" / "mie_cave_explorers.json").read_text(encoding="utf-8"))
    run = [k["next"] for k in cave["nodes"]["run_left"]["children"]]
    assert run.count("make_up") == 16 and run.count("fall_out") == 2 and len(run) == 20   # 10 / 80 / 10
