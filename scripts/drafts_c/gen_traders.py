"""Write the Island Traders draft (collection_lib.DRAFTS_C "draft_trd", TRD-01..13; the owner's spec of 2026-11-16/17)
as collection events, then format and check them:

    python scripts/drafts_c/gen_traders.py

The draft's shape is group C's with two more lines: the setup / Trade: / its outcome / Haggle: / the better haggle /
the worse haggle / Decline: / its outcome / the "nothing to trade" line.  Each event is built by gen_drafts_c.build
from its seven usual parts, then:
- the start is a branch: the setup (the question) when the village has what the trader asks for (`has_supply`, the
  most any trade of the event gives), else the "nothing to trade" page (cie-v6-binary.md 33);
- the requirement holds the same condition, so the natural roll and Pick Island Event offer the trader only then;
- Haggle leads to a branch of the better and the worse haggle, equally likely (the owner: "randomly better or
  worse");
- every [effect: trade N x for M y] is the "trade" effect (all or nothing).

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drafts_c_parse as P  # noqa: E402
import gen_drafts_c as G  # noqa: E402

lib = P.lib
cc = G.cc
SID = "draft_trd"
KEYS = ("S", "L1", "O1", "L2", "O2", "O2b", "L3", "O3", "N")


def events() -> list[P.Event]:
    out = []
    for r in P.rows(SID):
        h, e = r["lines"]
        code = P.raw(SID, h).split(".", 1)[0]
        assert P.raw(SID, h + 1).startswith("(picks "), code
        body = [n for n in range(h + 2, e + 1) if P.raw(SID, n).strip()]
        assert len(body) == len(KEYS), (code, len(body))
        out.append(P.Event(SID, r, code, h + 1, dict(zip(KEYS, body))))
    return out


def extra_page(ev: P.Event, key: str, name: str, ledger: list) -> dict:
    """A page the usual build does not make (the worse haggle, nothing to trade): the line's text, its effect."""
    n = ev.parts[key]
    s = P.raw(SID, n)
    fx = []
    m = G.EFFECT_RE.search(s)
    if m:
        fx = G.effect_for(ev.code, m.group(1), {})
        ledger.append({"src": G.L(n), "kind": "instruction", "text": m.group(0).strip(),
                       "why": "the draft's effect, never shown: the outcome's effect"})
        s = s[:m.start()] + s[m.end():]
    page = {"name": name, "text": G.escape_parens(lib.normalize_source_text(s)), "src": G.L(n)}
    if fx:
        page["effects"] = [dict(e, src=G.L(n)) for e in fx]
    to = G.text_only(P.raw(SID, n), fx)
    if to:
        page["text_only"] = [dict(t, src=G.L(n)) for t in to]
    return page


def build(ev: P.Event, ann: dict) -> tuple[dict, list[str]]:
    usual = replace(ev, parts={k: v for k, v in ev.parts.items() if k not in ("O2b", "N")})
    doc, problems, _g = G.build(usual, ann)
    ledger = doc["collection"]["ledger"]
    nodes = doc["nodes"]
    better = nodes.pop("o2")
    better["name"] = "Haggle, the better deal"
    worse = extra_page(ev, "O2b", "Haggle, the worse deal", ledger)
    nothing = extra_page(ev, "N", "Nothing to trade", ledger)
    trades = [e for nd in (nodes["o1"], better, worse) for e in nd.get("effects", []) if e["do"] == "trade"]
    gives = {e["give"] for e in trades}
    if len(trades) != 3 or len(gives) != 1:
        problems.append(f"{ev.code}: Trade and both Haggle lines each need one trade, giving the same good")
        return doc, problems
    # the village has what it would give, and its game keeps what it would get now (VV3's fruit: a tree planted;
    # The Tree of Life's supplies: invented): cie-v6-binary.md 33
    gets = sorted({e["get"] for e in trades})
    need = {"all": [{"has_supply": {"item": gives.pop(), "min": max(e["give_amount"] for e in trades)}}]
            + [{"has_supply": {"item": g, "min": 0}} for g in gets]}
    for c in nodes["setup"]["choices"]:
        if c["next"] == "o2":
            c["next"] = "haggle"
    nodes.update({"haggle": {"type": "branch", "name": "Haggle", "children": [{"next": "o2"}, {"next": "o2b"}]},
                  "o2": better, "o2b": worse, "nothing": nothing,
                  "trader": {"type": "branch", "name": "The trader's offer",
                             "children": [{"next": "setup", "if": need}], "else": "nothing"}})
    doc["nodes"] = {"trader": nodes.pop("trader"), **nodes}
    doc["start"] = "trader"
    doc["requirement"] = dict(doc["requirement"], **{"if": need})
    return doc, problems


def main() -> int:
    anns = P.read_annotations(SID)
    problems, paths = [], []
    for ev in events():
        doc, probs = build(ev, anns.get(ev.code, {}))
        problems += probs
        p = lib.DRAFTS_C_DIR / lib.DRAFTS_C[SID][2] / f"{ev.row['id']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    for p in problems:
        print("PROBLEM", p)
    rc = subprocess.call([sys.executable, str(P.ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
