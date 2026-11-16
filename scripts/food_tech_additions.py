"""Food and tech-point gains and losses where an outcome's own text already says food or knowledge changes hands.

The owner's request (v1.35.97, 2026-11-15): "Where the text fits".  Only outcomes whose wording implies it -- a catch,
harvest or feast shared; stores spoiled, eaten, washed away or given away; a new idea, method or discovery the
village keeps; notes, records, evidence or a teacher's method lost, broken or forgotten -- get a food or tech
effect.  No text, title, choice, weight or other effect changes.  An outcome that already has a food / tech effect,
or whose path already gives one of that kind, gets nothing.  The stock games' events and the owner's More Island
Events are not collection files and are never touched.

Sizes: "small" by default; "normal" only where the text says it is big ("a major medical discovery").  Every effect
is scaled (design A3) and carries its outcome node's own src, like the collection's other effects.

ADDITIONS is the record (one row per effect: event id, node, kind, size, loss, the text that justifies it).  The
generators of the Companion Anthology, the Living Event Engine and Beyond the Horizon / Role Models apply it as they
write (companion_common / living_common / hzrm_common write_and_check), so a regeneration keeps every row; the
Grand collection's (V28) files have no generator, so `python scripts/food_tech_additions.py` applies the table to
the files on disk (every source; it is idempotent) and rewrites docs/event-collection/food-tech-log.md.

    python scripts/food_tech_additions.py            # apply to the collection files, write the log
    python scripts/food_tech_additions.py --check    # report only (nothing written)

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_DIR = ROOT / "data" / "event_collection"
LOG = ROOT / "docs" / "event-collection" / "food-tech-log.md"

FG, FL, TG, TL = ("food", False), ("food", True), ("tech", False), ("tech", True)

# (event id, node, (kind, loss), size, why: the outcome's own words)
ADDITIONS: list[tuple[str, str, tuple[str, bool], str, str]] = [
    # ---- Companion Anthology ----------------------------------------------------------------------------------------
    ("c5a001_kiln_secret", "o1", TG, "small", "A new firing technique yields sturdy glazed jars."),
    ("c5a009_alchemist_debt", "o1", TG, "small", "They invent a brilliant substitute using plants and minerals."),
    ("c5a012_great_herbarium", "o2", TL, "small", "Poor storage ruins a season of delicate specimens."),
    ("c5a021_sounding_cavern", "o1", TG, "small", "Researchers map the echoes and infer hidden passages."),
    ("c5a025_endless_pattern", "o1", TG, "small", "The pattern inspires a useful counting method."),
    ("c5a026_bridge_calc", "o3", TG, "small", "The team discovers that the shortest bridge is not the safest."),
    ("c5a038_deepwater_shell", "o1", TG, "small", "A shallow-water prototype reveals a new way to observe marine life."),
    ("c5a042_vessel_no_oars", "o3", TG, "small", "The craft carries a map of waters beyond known Isola."),
    ("c5a045_cartographer", "o1", TG, "small", "The map reveals a promising unexplored route."),
    ("c5dn024_ring_mushrooms", "e1", TG, "small", "Researchers document an unusual growth pattern."),
    ("c5dn026_mushroom_isnt", "e1", TG, "small", "Discover a rare plant structure."),
    ("c5ev013_fisher", "e2", FG, "small", "The catch inspires a new stew."),
    ("c5ev015_pig_feast", "e1", FG, "small", "Neighbors share roasted meat, roots and fruit."),
    ("c5ev024_canoe_two_bows", "e2", TG, "small", "The crew discovers it handles differently in crosswinds."),
    ("lbl076_cave_breathes", "e3", TG, "small", "A cautious expedition maps an unfamiliar chamber."),
    ("lbl104_invention", "e2", TG, "small", "A practical use is discovered later."),
    ("sss028_sail_beyond", "a", TG, "small", "The expedition remains a future ambition while coastal surveys improve knowledge."),
    ("sss038_biggles_tax", "b", FG, "small", "The coconuts are collected for a feast, but nobody learns who wrote the sign."),
    ("sss039_return_unknown", "a", TG, "small", "Craftspeople learn a new knot, but cannot identify the builder."),
    # ---- Living Event Engine ----------------------------------------------------------------------------------------
    ("lvauth29_apprentice", "d2", TL, "small", "The apprentice mourns the loss of a promising discovery."),
    ("lvcir07_octopus_pot", "c1", FG, "small", "The octopus escapes unharmed while fishers still catch their supper."),
    ("lvcir09_fisher_thanks", "b1", FG, "small", "The apprentice carefully uses the entire catch and questions empty rituals."),
    ("lvcir17_healer_beetle", "a1", FG, "small", "The harvest improves, but birds that ate the beetles visit less often."),
    ("lvcir19_departed", "a2", FG, "small", "The first harvest becomes a quiet occasion for remembrance."),
    ("lvcir21_tree_fallen", "b1", FG, "small", "Birds and insects feast, while the village keeps a smaller share."),
    ("lvcir21_tree_fallen", "c1", FG, "small", "The village adapts its harvest to the year's abundance."),
    ("lvlife11_empty_granary", "a2", TG, "small", "The village learns to protect drying food from insects."),
    ("lvlife11_empty_granary", "c1", TG, "small", "The village learns which method suits each food."),
    ("lvlife12_sealed_jar", "c1", TG, "small", "Families learn which foods keep reliably."),
    ("lvlife13_salt_tide", "a1", FG, "small", "The preserved fish feeds the village during rough weather."),
    ("lvlife14_field_grew", "b1", FG, "small", "The next harvest improves, but the reason remains uncertain."),
    ("lvlife16_farm_above", "c2", FG, "small", "The harvest succeeds, but fishers worry about damage below."),
    ("lvlife22_map_old_path", "a2", TG, "small", "The explorers reach the destination and improve the map."),
    ("lvlife37_winter_cloak", "b1", TG, "small", "The cloth performs well, and the weavers learn a new technique."),
    ("lvlife37_winter_cloak", "c1", TG, "small", "The weavers gain knowledge from another land."),
    ("lvlife43_library_hands", "b2", TL, "small", "An apprentice forgets the technique after the teacher leaves."),
    ("lvmed01_borrowed_organ", "c2", TG, "small", "The research yields a useful wound-care insight but no safe transplant."),
    ("lvmed04_draught", "c2", TG, "small", "A safer method of easing pain is found, though it cannot guarantee comfort."),
    ("lvmed31_choose_healer", "a1", TG, "small", "A new technique helps a patient, but its risks remain unknown."),
    ("lvuns15_mask_forest", "c2", TL, "small", "A storm destroys the evidence before it can be examined."),
    ("lvuns16_scientist", "a1", TG, "small", "The survey documents several rare ordinary animals."),
    ("lvuns21_gods_need", "b1", FG, "small", "A fortunate harvest inspires conflicting interpretations."),
    ("lvuns29_legend_fire", "b1", TG, "small", "The scientists reproduce one useful fire-making technique."),
    ("lvuns30_creature", "b1", TG, "small", "The village celebrates the discovery."),
    ("lvway06_mystery", "b1", TG, "small", "The trial reveals which storage method works best."),
    ("lvway20_hungry", "a2", FG, "small", "The feast inspires neighbors to share hidden supplies."),
    ("lvway21_argument_over", "c1", TG, "small", "The expedition improves the map and preserves the story."),
    ("lvway26_elder_changed", "b1", FG, "small", "The harvest improves without public conflict."),
    ("lvway27_parent_knew", "b1", TG, "small", "The villager returns with valuable knowledge."),
    # ---- Beyond the Horizon / Role Models ---------------------------------------------------------------------------
    ("hz054_water_arrives", "c1", TG, "small", "The villagers map their own springs and agree that protecting the watershed matters regardless of technology."),
    ("rm07_fisher_restraint", "a1", FG, "small", "The fisher returns with a modest catch and leaves the remaining fish undisturbed."),
    ("rm18_tree_fruit", "d1", FG, "small", "Several families enjoy a small portion of fresh fruit."),
    # ---- Grand collection (V28) -------------------------------------------------------------------------------------
    ("all_conundrums", "a5", TG, "small", "the villagers learn to ask better questions and to record what happened rather than what they hoped would happen."),
    ("all_conundrums", "c1", TG, "small", "The single proposal is a simple tool for lifting hot cooking pots without burning one's hands. The cook tests it and approves."),
    ("all_conundrums", "c4", TG, "small", "\"You rediscovered something worth remembering,\""),
    ("all_inexplicable_idea", "a1", TG, "small", "The idea solves a practical problem with ordinary materials ... (Inventor) is offered a chance to teach the method."),
    ("all_inexplicable_idea", "c1", TG, "small", "(Inventor) returns weeks later with a smaller, more practical design. The council approves it."),
    ("all_invention", "t2", TG, "small", "The invention fails, but the observations reveal something useful about material strength."),
    ("all_invention_showcase", "a4", TG, "small", "a particular knot holds far more weight than the others. The builders test the knot, improve it, and teach"),
    ("all_invention_showcase", "c8", TG, "small", "\"what if we used the same arrangement of vines to lift a heavy stone?\" ... The builders try it."),
    ("all_physics_defying", "b1_more", TG, "small", "the village adopts the new technique after independent testing."),
    ("all_secret_of_life", "a4_2", TG, "small", "The healers test the fibers safely and discover a useful way to bind splints."),
    ("all_secret_of_life", "b5_2", TG, "small", "the discovery of a way to extinguish flames. (Subject) begins taking notes"),
    ("all_secret_of_life", "c6_2", TG, "small", "discovers an ingenious tensioned-vine mechanism. \"It doesn't live,\" the builder says, \"but it could lift water.\""),
    ("all_v20_d2_no_such", "a1", TG, "normal", "It works; the village celebrates a major medical discovery."),
    ("all_v20_r1_should_not", "a1", TL, "small", "The object is smashed. Researchers lament the lost evidence"),
    ("all_v20_r1_should_not", "a4", TG, "small", "A useful component inspires a new island-made tool."),
    ("all_v20_r1_should_not", "b1", TG, "small", "(Finder) discovers a practical function; craftspeople attempt to imitate it using island materials."),
    ("all_v20_r3_isola", "c2", TG, "small", "A researcher records the discovery despite an order of silence."),
    ("all_v21_c1_potters", "a5", TG, "small", "a healer discovers it is useful for measuring small amounts of water. (Potter) becomes an unexpectedly celebrated innovator."),
    ("all_v22_4_parents", "d2", FL, "small", "(Child) gives away all the family's prepared snacks, including the portion meant for (Parent)."),
    ("all_v24_revolutionary", "a1_food", TG, "small", "Within days nearly everyone adopts the invention or celebrates the discovery."),
    ("all_v24_revolutionary", "a1_sci", TG, "small", "Within days nearly everyone adopts the invention or celebrates the discovery."),
    ("all_v24_revolutionary", "a1_eng", TG, "small", "Within days nearly everyone adopts the invention or celebrates the discovery."),
    ("all_v24_revolutionary", "a1_trade", TG, "small", "Within days nearly everyone adopts the invention or celebrates the discovery."),
    ("all_v24_revolutionary", "a1_art", TG, "small", "Within days nearly everyone adopts the invention or celebrates the discovery."),
    ("all_v24_revolutionary", "a4_food", TG, "small", "The innovation solves a longstanding village problem."),
    ("all_v24_revolutionary", "a4_sci", TG, "small", "The innovation solves a longstanding village problem."),
    ("all_v24_revolutionary", "a4_eng", TG, "small", "The innovation solves a longstanding village problem."),
    ("all_v24_revolutionary", "a4_trade", TG, "small", "The innovation solves a longstanding village problem."),
    ("all_v24_revolutionary", "a4_art", TG, "small", "The innovation solves a longstanding village problem."),
    ("all_v24_revolutionary", "c3", TL, "small", "destroys the demonstration apparatus. Nearby villagers retreat; damaged equipment must be replaced."),
    ("all_v24_revolutionary", "d4", TL, "small", "The only record is damaged or misplaced. The innovation vanishes from village memory."),
    ("all_v24_revolutionary", "e1", TG, "small", "The elders approve practical use, training, or preservation of the discovery in the village records."),
    ("all_v27_24_explorer", "a", TG, "small", "They return with a new map and a chastened attitude."),
    ("vv2_cooking_contest", "v13a_b5", TG, "small", "(judge) listens, tastes, and asks for the method to be recorded so it is not lost."),
    ("vv2_hut_sharing_negotiation", "e2", TG, "small", "{@Chief} asks the builders to write down what they learned before the next group of newcomers arrives."),
    ("vv3_gardening_contest", "p1", TG, "small", "The villagers learn which designs suit which purposes."),
    ("vv3_v17_cooking", "b2", FG, "small", "Both meals are excellent and the Chief orders a shared feast."),
    ("vv4_breadfruit_breakdown", "o4", TG, "small", "The cooks preserve the recipe in the village's records."),
    ("vv4_v17_cooking", "a2", FL, "small", "A catastrophically pungent pot drives everyone away from the feast; it is discarded and the cooks must start again."),
    ("vv5_v17_cooking", "c1", FG, "small", "A magnificent joint feast wins over most of the audience, though a few refuse to eat."),
]

# The Living Catalogue's study templates (companion cat/): the record the village keeps gains knowledge.
_CAT_FISH = ["cat001_shark", "cat002_catfish", "cat003_arrowfish", "cat004_snout", "cat005_fatfish", "cat006_snooper",
             "cat007_goldshark", "cat008_fire_arrow", "cat009_fruitfish", "cat010_flashfish", "cat011_goldbulb",
             "cat012_comet", "cat013_stickfish", "cat014_grouper", "cat015_leaffish", "cat016_carp", "cat017_beta",
             "cat018_pigmy", "cat019_bananafish", "cat020_quicksilver", "cat021_spotanus", "cat022_clownfish",
             "cat023_discus", "cat024_bicolor", "cat025_trigger", "cat026_surgeonfish", "cat027_tang", "cat028_idle"]
_CAT_PLANTS = ["cat057_reptans", "cat058_scandens", "cat059_grass", "cat060_orchid", "cat061_astera",
               "cat062_gladiatus", "cat063_fern", "cat064_ananas", "cat065_maranta", "cat066_fanleaf",
               "cat067_lemonbush", "cat068_bamboo", "cat069_maple", "cat070_rare_oak", "cat071_pipe_cactus",
               "cat072_pear_cactus", "cat073_ball_cactus", "cat074_glaber", "cat075_tigerfern", "cat076_pitcher",
               "cat077_weeper", "cat078_multiflora", "cat079_ridgeball"]
ADDITIONS += [(e, "c", TG, "small", "The record gains anatomical detail ... whether the knowledge justified the loss")
              for e in _CAT_FISH]
ADDITIONS += [(e, "d", TG, "small", "A detailed herbarium specimen results") for e in _CAT_PLANTS]


def effect(node: dict, kind: tuple[str, bool], size: str) -> dict:
    do, loss = kind
    e = {"do": do, "size": size, "scaled": True}
    if loss:
        e["loss"] = True
    e["src"] = node["src"]
    return e


def _by_event() -> dict[str, list[tuple[str, tuple[str, bool], str, str]]]:
    out: dict[str, list] = {}
    for eid, node, kind, size, why in ADDITIONS:
        out.setdefault(eid, []).append((node, kind, size, why))
    return out


def _edges(doc: dict) -> dict[str, set[str]]:
    out = {}
    for nid, n in doc.get("nodes", {}).items():
        nxt = set()
        for c in (n.get("children") or []) + (n.get("choices") or []):
            for k in ("next", "else"):
                if c.get(k):
                    nxt.add(c[k])
        out[nid] = nxt
    return out


def _reach(edges: dict[str, set[str]], start: str) -> set[str]:
    seen, todo = set(), [start]
    while todo:
        x = todo.pop()
        for y in edges.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return seen


def problems_for(doc: dict, rows) -> list[str]:
    """Why a row cannot be applied (empty = fine): the node is missing or has no src, or the node, a node before it
    or a node after it already has an effect of that kind (other than the row's own)."""
    out = []
    nodes = doc.get("nodes", {})
    edges = _edges(doc)
    mine = {(node, kind[0]) for node, kind, _, _ in rows}
    for node, kind, size, _ in rows:
        n = nodes.get(node)
        if n is None:
            out.append(f"node {node} is missing")
            continue
        if not n.get("src"):
            out.append(f"node {node} has no src")
        down = _reach(edges, node)
        up = {a for a in nodes if node in _reach(edges, a)}
        for other in {node} | down | up:
            if other != node and (other, kind[0]) in mine:
                out.append(f"node {node}: node {other} on the same path is also a {kind[0]} row")
            for e in nodes[other].get("effects", []) or []:
                if e.get("do") == kind[0]:
                    out.append(f"node {node}: {'it' if other == node else 'node ' + other} already has a {kind[0]} effect")
    return out


def apply(doc: dict) -> dict:
    """Add this event's rows to doc (in place; idempotent) and return it.  Raises on a row that cannot be applied."""
    col = doc.get("collection") or {}
    rows = _by_event().get(col.get("id"))
    if not rows:
        return doc
    nodes = doc["nodes"]
    for node, kind, size, _ in rows:
        n = nodes.get(node)
        if n is None:
            raise SystemExit(f"food_tech_additions: {col.get('id')}: node {node} is missing")
        effs = n.setdefault("effects", [])
        if any(e.get("do") == kind[0] for e in effs):
            continue              # already applied (or already given by its generator)
        effs.append(effect(n, kind, size))
    return doc


def collection_files() -> dict[str, Path]:
    out = {}
    for p in sorted(COLLECTION_DIR.rglob("*.json")):
        if p.name in ("manifest.json", "shared_pools.json"):
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        eid = (doc.get("collection") or {}).get("id")
        if eid:
            out[eid] = p
    return out


def write_log(files: dict[str, Path], docs: dict[str, dict]) -> None:
    by_src: dict[str, list] = {}
    for eid, node, kind, size, why in ADDITIONS:
        src = docs[eid]["collection"].get("source", "v28")
        by_src.setdefault(src, []).append((eid, node, kind, size, why))
    names = {"v28": "Grand collection (V28)", "companion": "Companion Anthology", "living": "Living Event Engine",
             "horizon": "Beyond the Horizon", "rolemodels": "Role Models and Good Examples"}
    lines = ["# Food and tech where the text fits (v1.35.97)", "",
             "The owner's request (2026-11-15, \"Where the text fits\"): outcomes whose own words already say food or",
             "knowledge changes hands get a scaled food or tech effect. No text, title, choice, weight or other effect",
             "changed. The table is `scripts/food_tech_additions.py` ADDITIONS (generated into this file by",
             "`python scripts/food_tech_additions.py`); the companion, living and horizon / role-model generators apply",
             "it as they write, and the Grand collection's files carry it directly.", "",
             "Sizes: small food is the collection's small scaled amount (design A3); a loss is the same range negated.", ""]
    total = {FG: 0, FL: 0, TG: 0, TL: 0}
    for src in ("v28", "companion", "living", "horizon", "rolemodels"):
        rows = by_src.get(src, [])
        if not rows:
            continue
        lines += [f"## {names[src]} ({len(rows)})", "", "| Event | Node | Effect | Why (the outcome's text) |",
                  "|---|---|---|---|"]
        for eid, node, kind, size, why in rows:
            total[kind] += 1
            what = f"{kind[0]} {'loss' if kind[1] else 'gain'} {size} (scaled)"
            lines.append(f"| `{eid}` | {node} | {what} | {why.replace('|', '/')} |")
        lines.append("")
    lines.insert(9, f"Totals: food gain {total[FG]}, food loss {total[FL]}, tech gain {total[TG]}, "
                    f"tech loss {total[TL]} ({len(ADDITIONS)} effects).")
    lines.insert(10, "")
    LOG.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "scripts"))
    import collection_check as cc  # noqa: E402

    seen = set()
    for eid, node, kind, *_ in ADDITIONS:
        if (eid, node, kind[0]) in seen:
            print(f"duplicate row {eid} {node} {kind[0]}")
            return 1
        seen.add((eid, node, kind[0]))
    files = collection_files()
    docs, bad = {}, 0
    for eid, rows in _by_event().items():
        if eid not in files:
            print(f"{eid}: no collection file")
            bad += 1
            continue
        doc = json.loads(files[eid].read_text(encoding="utf-8"))
        docs[eid] = doc
        # a node's own earlier application is not a conflict: check against the file with this table's rows removed
        clean = json.loads(json.dumps(doc))
        for node, kind, _, _ in rows:
            n = clean["nodes"].get(node)
            if n and n.get("effects"):
                n["effects"] = [e for e in n["effects"] if not (e.get("do") == kind[0] and e.get("src") == n.get("src")
                                                                and e.get("size") in cc.SIZES)]
        for p in problems_for(clean, rows):
            print(f"{eid}: {p}")
            bad += 1
    if bad:
        return 1
    if args.check:
        print(f"{len(ADDITIONS)} rows over {len(docs)} events: all apply")
        return 0
    changed = 0
    for eid, doc in docs.items():
        before = cc.canonical(doc)
        after = cc.canonical(apply(doc))
        if after != before:
            files[eid].write_text(after, encoding="utf-8", newline="\n")
            changed += 1
    write_log(files, docs)
    print(f"{len(ADDITIONS)} rows over {len(docs)} events; {changed} files changed; log {LOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
