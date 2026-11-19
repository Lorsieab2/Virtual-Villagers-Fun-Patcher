"""The existing added events whose words give or take The Tree of Life's cutting tools, soap or cloth (the owner,
2026-11-17): each outcome below makes the "supply" effect (docs/event-collection/cie-v6-binary.md 38) its words say.

THE OWNER'S RULES: where an existing added event's text says the village gains, loses, uses, breaks or finds a cutting
tool, soap or cloth (a "sack" is a cloth bolt: the sacks are made per trip), that outcome gets the matching real effect
-- tools and cloth 0..6 (0..99 with Up to 99 Cutting Tools/Soap/Cloth), soap 0..99, never below 0, nothing before the
item is invented (the engine's rule) -- and the text never changes.  The effect acts only in The Tree of Life: these
events are for all five games, and in the other four their words stay story only.

WHY A TABLE: the files are written by their own generators (scripts/anthology_new, drafts_c, drafts_d, living_vols)
from the frozen sources, which mark no such effect.  `python scripts/collection_check.py --format` (which every
generator ends with) adds the effects listed here, and the check refuses a listed file that lacks one, so a rebuilt
file always keeps them.  The Living mixer's outcome lines are scripts/living_bank_build.py SUPPLY.

Each entry: event id -> {node id: [effects]}; an effect's src is its node's own src (the outcome line that says it).
"""
from __future__ import annotations

# The audit (2026-11-17) of every added event for The Tree of Life whose words mention a sack, soap, a cutting tool or
# cloth; the rest only mention them (clothes worn, a cloth wrap, a personal knife used and kept) and stay story only.
SUPPLY = {
    # The Market of Repairs, "Repair Tools": "One damaged blade is retired for safety."
    "anexp61_market_repairs": {"a2": [{"do": "supply", "item": "cutting_tools", "min": -1, "max": -1}]},
    # Hornets by the Path, "Move It at Night": the nest is wrapped in the sack and left in a far tree.
    "nat36_hornets_path": {"o1": [{"do": "supply", "item": "cloth", "min": -1, "max": -1}]},
    # The Rare Dye Vine, "Harvest a small portion": "The weavers produce a brilliant cloth".
    "lvlife20_rare_dye_vine": {"a1": [{"do": "supply", "item": "cloth", "min": 1, "max": 1}]},
    # The Rhythm of the Bark Beater, ending 3: "The finished cloth is so thin that light shines through it."
    "tim133_rhythm_bark": {"e3": [{"do": "supply", "item": "cloth", "min": 1, "max": 1}]},
}


def wanted(doc: dict) -> dict:
    """{node id: [effects]} the table lists for this file (empty when none)."""
    col = doc.get("collection") if isinstance(doc.get("collection"), dict) else {}
    return SUPPLY.get(col.get("id"), {})


def apply(doc: dict) -> None:
    """Add each listed effect to its node (once), its src the node's."""
    for nid, effects in wanted(doc).items():
        node = doc.get("nodes", {}).get(nid)
        if not isinstance(node, dict):
            continue
        have = node.setdefault("effects", [])
        for e in effects:
            e = dict(e, src=node.get("src"))
            if e not in have:
                have.append(e)


def missing(doc: dict) -> list[str]:
    """The listed effects the file lacks."""
    out = []
    for nid, effects in wanted(doc).items():
        node = doc.get("nodes", {}).get(nid)
        have = [{k: v for k, v in e.items() if k != "src"} for e in (node or {}).get("effects", []) or []]
        for e in effects:
            if node is None or e not in have:
                out.append(f"node {nid}: {e}")
    return out
