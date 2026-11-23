"""Text-implied outcome effects (the owner's outcomes pass, v1.35.97).

The owner asked for the added island events to get the game effects their own outcome text already implies, sized like
the stock island events ("go look at the vanilla island events and emulate how those work").  The effects are kept
apart from the events' sources, one line per effect, in the owner's script-readable form:

    <file> | <node> | <OWNER WORDS> | "<the outcome's own words that justify it>" | <the effect as JSON>

`<file>` is the event's path under data/event_collection/.  The lists are data/event_collection/outcome_effects/*.txt
(one file per source).  Lines for events or effect kinds that are not on this branch yet live in
data/event_collection/outcome_effects/pending/ and are never read here: move a pending file up after its branch
merges, then run this script.

Every generator adds the effects as it writes a file (`collection_check.with_outcome_effects`), and collection_check
fails a file that lacks one (`check_outcome_effects`).  Nothing here changes any text.

    python scripts/outcome_effects.py            add the listed effects to every listed file (idempotent)
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_DIR = ROOT / "data" / "event_collection"
LISTS = COLLECTION_DIR / "outcome_effects"


def parse_line(line: str, where: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(" | ")
    if len(parts) < 5:
        raise ValueError(f"{where}: expected <file> | <node> | <words> | \"<quote>\" | <JSON>")
    effect = json.loads(parts[-1])
    if not isinstance(effect, dict) or "do" not in effect:
        raise ValueError(f"{where}: the last field is an effect object with \"do\"")
    return {"file": parts[0].strip(), "node": parts[1].strip(), "words": parts[2].strip(),
            "quote": " | ".join(parts[3:-1]).strip(), "effect": effect}


@lru_cache(maxsize=1)
def table() -> dict[str, dict[str, list[dict]]]:
    """{file: {node: [effect, ...]}} from every active list."""
    out: dict[str, dict[str, list[dict]]] = {}
    for p in sorted(LISTS.glob("*.txt")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            row = parse_line(line, f"{p.name}:{i}")
            if row:
                out.setdefault(row["file"], {}).setdefault(row["node"], []).append(row["effect"])
    return out


def rel(path: Path) -> str:
    return Path(path).resolve().relative_to(COLLECTION_DIR).as_posix()


def _rel_or_none(path: Path) -> str | None:
    try:
        return rel(path)
    except ValueError:
        return None


def wanted(doc: dict, path: Path) -> list[tuple[str, dict]]:
    """The (node, effect) pairs listed for this file, each with the node's own src (the text that implies it)."""
    try:
        nodes = table().get(rel(path), {})
    except ValueError:
        return []
    out = []
    all_nodes = doc.get("nodes", {})
    for nid, effects in nodes.items():
        node = all_nodes.get(fx_id(nid)) or all_nodes.get(nid)
        for e in effects:
            e = dict(e)
            if node is not None and node.get("src"):
                e["src"] = node["src"]
            out.append((nid, e))
    return out


# The owner (2026-11-18): each effect this pass adds happens half the time; the other half is the text alone.  The
# outcome node X becomes a silent, equally weighted chance split (the format's own "type": "branch", as authoring-
# rules.md 8 resolves an outcome with two results) to two copies of X's page: X__fx (X plus the added effects) and
# X__text (X as it was).  Everything that led to X still leads to X; X's own effects stay on both copies (100%).
FX, TEXT = "__fx", "__text"


def fx_id(nid: str) -> str:
    return nid + FX


def text_id(nid: str) -> str:
    return nid + TEXT


# Files whose graph is too big to split (more than the checker's 200,000 histories once doubled): the owner
# (2026-11-19) "if neither works, give them without the 50% chance" -- the effects go on the page itself.
NO_SPLIT = {"original/vv2_cooking_contest.json"}


def _pref_games(doc: dict, effects: list[dict]) -> list[int] | None:
    """The event's games whose preference lists hold every like / dislike word of `effects` (the owner, 2026-11-19:
    "give them in the games that have them"), or None when every game does."""
    words = [e["preference"] for e in effects if e.get("do") == "preference" and e.get("preference") not in
             (None, "random")]
    if not words:
        return None
    sys.path.insert(0, str(ROOT / "src"))
    import vv_cie_graph as cg  # noqa: E402
    games = doc.get("games", [])
    have = [g for g in games if all(w in cg.GAMES[g].preferences for w in words)]
    return None if have == games else have


def split(doc: dict, nid: str) -> dict | None:
    """X's effects copy, making the split first when X is still a plain page."""
    nodes = doc.get("nodes", {})
    if nid in nodes and doc.get("_no_split"):
        return nodes[nid]
    if fx_id(nid) in nodes:
        return nodes[fx_id(nid)]
    node = nodes.get(nid)
    if node is None:
        return None
    nodes[fx_id(nid)] = json.loads(json.dumps(node))
    nodes[text_id(nid)] = json.loads(json.dumps(node))
    nodes[nid] = {"type": "branch", "name": node.get("name", "The 50 percent chance"),
                  "children": [{"next": fx_id(nid)}, {"next": text_id(nid)}]}
    return nodes[fx_id(nid)]


# The owner (2026-11-18): "if an effect happens, it should say at the end of the event popup" -- always, on every
# added event, old effects and new: each node with an effect shows the engine's result lines (cie-v6-binary.md 25,
# "auto_text").  A death or a disappearance takes its other wording from the page's own words (the "line" key):
# "<R> suffers fatal injuries." where the text tells of an accident or injury, "<R> leaves the village." where the
# villager goes of their own accord.
LEAVES = re.compile(r"\b(leaves?|left|leaving|depart\w*|goes? away|went away|sets? (?:out|off|sail)|set (?:out|off)"
                    r"|sails? away|sailed away|walks? away|walked away|moves? away|chooses? to go|decides? to go"
                    r"|goes? to live|says? goodbye|bids? farewell)\b", re.I)
INJURIES = re.compile(r"\b(falls?|fell|fallen|injur\w*|wound\w*|accident\w*|crush\w*|struck|drown\w*|tumbl\w*"
                      r"|slips?|slipped|collaps\w*|landslide|rockfall|broken|gored|mauled|burn(?:s|ed|t)?)\b", re.I)


# A page whose death itself is told as peaceful ("dies peacefully in (his/her) sleep", "is found in the morning,
# sitting peacefully against the rocks") never says "suffers fatal injuries", whatever else it mentions (a knot "that
# never slips", a torch "burnt out"): it keeps the plain "<R> dies." (the lines audit, 2026-11-22).  Only the death
# verb followed closely by the peaceful words counts, so a violent death that mentions sleep ("the tree falls on the
# hut where (name) is sleeping") keeps its injury line.
PEACEFUL = re.compile(r"\b(?:dies|died|is found|was found|passes away|passed away|slips away)\b[^.!?]{0,40}?"
                      r"\b(?:peacefully|in (?:\([^()]*\)|his|her|their) sleep)", re.I)


def _page_words(node: dict) -> str:
    return " ".join([node.get("text") or ""] + [v.get("text") or "" for v in node.get("variants") or []])


def wording(node: dict, e: dict) -> str | None:
    """The other wording a kill / vanish on this page takes from the page's own words, or None."""
    if e.get("do") == "kill" and INJURIES.search(_page_words(node)) and not PEACEFUL.search(_page_words(node)):
        return "injuries"
    if e.get("do") == "vanish" and LEAVES.search(_page_words(node)) and \
            not re.search(r"\b(missing|lost|taken|swept|never found)\b", _page_words(node), re.I):
        return "leaves"
    return None


def finish(doc: dict) -> dict:
    """Every page with an effect shows its result lines; a kill / vanish gets the page's wording."""
    for node in doc.get("nodes", {}).values():
        effects = node.get("effects") or []
        if not effects or node.get("type") in ("question", "branch"):
            continue
        node["auto_text"] = True
        for e in effects:
            w = wording(node, e)
            if w:
                e["line"] = w
            else:
                e.pop("line", None)
    return doc


def apply(doc: dict, path: Path) -> dict:
    """Add each listed effect, at 50%, that its node does not hold yet (idempotent), then finish the file.  A
    missing node is left to the check."""
    try:
        whole = rel(path) in NO_SPLIT
    except ValueError:
        whole = False
    if whole:
        doc["_no_split"] = True
    for nid, e in wanted(doc, path):
        node = split(doc, nid)
        if node is None:
            continue
        effects = node.setdefault("effects", [])
        if e not in effects:
            effects.append(e)
    doc.pop("_no_split", None)
    for nid in table().get(_rel_or_none(path) or "", {}):
        head, fx = doc.get("nodes", {}).get(nid), doc.get("nodes", {}).get(fx_id(nid))
        if head is None or fx is None or head.get("type") != "branch":
            continue
        games = _pref_games(doc, table()[_rel_or_none(path)][nid])   # the added effects' words only
        first = head["children"][0]
        if games is None:
            first.pop("if", None)
        else:
            first["if"] = {"game": games}    # a like the game lacks: that game keeps the text alone
    try:
        rel(path)
    except ValueError:
        return doc
    return finish(doc) if doc.get("format") == "vvfp-cie-graph" else doc


def missing(doc: dict, path: Path) -> list[str]:
    out = []
    nodes = doc.get("nodes", {})
    whole = _rel_or_none(path) in NO_SPLIT
    for nid, e in wanted(doc, path):
        node, plain, head = nodes.get(fx_id(nid)), nodes.get(text_id(nid)), nodes.get(nid)
        if whole:
            if head is None or e not in (head.get("effects") or []):
                out.append(f"node {nid}: lacks the listed outcome effect {json.dumps(e)} "
                           "(python scripts/outcome_effects.py)")
            continue
        if node is None or plain is None or head is None:
            out.append(f"node {nid}: listed in outcome_effects but not split into {fx_id(nid)} / {text_id(nid)} "
                       "(python scripts/outcome_effects.py)")
        elif head.get("type") != "branch" or [c.get("next") for c in head.get("children", [])] != \
                [fx_id(nid), text_id(nid)] or any("weight" in c for c in head["children"]):
            out.append(f"node {nid}: the 50% split is not an even branch to {fx_id(nid)} and {text_id(nid)}")
        elif head.get("effects"):
            out.append(f"node {nid}: the 50% branch itself holds effects (they belong on {fx_id(nid)} and "
                       f"{text_id(nid)})")
        elif e not in (node.get("effects") or []):
            out.append(f"node {nid}: lacks the listed outcome effect {json.dumps(e)} "
                       "(python scripts/outcome_effects.py)")
        elif e in (plain.get("effects") or []):
            out.append(f"node {nid}: the text-only copy {text_id(nid)} holds the added effect")
    try:
        rel(path)
    except ValueError:
        return out                     # a file outside the collection (a test's own): its author's choice
    if doc.get("format") == "vvfp-cie-graph" and \
            json.dumps(finish(json.loads(json.dumps(doc))), sort_keys=True) != json.dumps(doc, sort_keys=True):
        out.append("a page with an effect lacks its result lines (auto_text) or a death / leaving wording "
                   "(python scripts/outcome_effects.py)")
    return out


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import collection_check as cc  # noqa: E402
    n = 0
    for f in sorted(table()):
        if not (COLLECTION_DIR / f).exists():
            print(f"MISSING {f}")
    for p in cc.collection_files():
        f = rel(p)
        doc = json.loads(p.read_text(encoding="utf-8"))
        text = cc.canonical(apply(doc, p))
        if text != p.read_text(encoding="utf-8"):
            p.write_text(text, encoding="utf-8", newline="\n")
            n += 1
            print(f"updated {f}")
    print(f"{n} file(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
