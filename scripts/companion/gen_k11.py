"""Chunk K11: write The Living Catalogue's foliage and flowers, events 057-116 (companion L7781-8499), as
data/event_collection/companion/cat/cat<NNN>_<slug>.json, then format and check them.

THE SOURCE'S FORMAT (L7107 "CHOICES ARE EXCLUSIVE; EACH HAS A DISTINCT OUTCOME"; 11 lines per event), as gen_k10.py:
  EVENT NNN - Title / Premise: / 4 x (CHOICE: label / OUTCOME: text) / Context / follow-up: (a designer note)
- A true 1:1 choice: the premise is the question page with the four labels, and each label leads to its own answer
  page.  "Premise:", "CHOICE:" and "OUTCOME:" are structural markers; "Context / follow-up:" is a designer note.
- Two templates with the species name swapped: 057-079 "The <Foliage> Study" (series cat_foliage) and 080-116
  "The <Flower> Bloom" (series cat_flowers).  Each series counts as ONE event in the rare roll (draw weight 1).
- The species names are the Fish and Plant Tycoon names as Isolan species (the owner's choice), verbatim.

CASTING: the text names nobody (rule 10).  "A botanist" (057-079) is a villager with some Farming (gen_k9's botanist).
"A dye maker" and "a naturalist" (080-116) are villagers; the naturalist has some Research (gen_k9's naturalist).

EFFECTS (V28 consequence rules; the owner 2026-11-14: hands-on study earns a small skill):
- Foliage: C "Cultivate a cutting if feasible": the botanist's small Farming (gen_k9 124-129: a propagated cutting);
  D "Uproot and dry the entire plant" ("A detailed ... specimen results"): the botanist's small Research (gen_k10's
  preserved specimen).  A (a drawing in place) and B (a fallen leaf, maybe too damaged) are observation only.
- Flowers: A "Observe through the flowering period" ("A record of pollinators and scent emerges"): the naturalist's
  small Research; B (a fallen petal "inspires a delicate ink") and D (a substitute "prompting a new palette"): the
  dye maker's small Research (gen_k9 135 and 149: a new dye or blend).  C (the bloom harvested) is the product only.
- Nobody is hurt: the plant that is lost or sets no seed is a plant (text only).

GRAMMAR (docs/event-collection/grammar-fixes.md, companion section): "a Arthurium / a Anagallis / a Indigoberry" ->
"an ..." (L7902, L8022, L8034).

SENSITIVITY: none.  The owner (2026-11-15): "herbarium" and "ecological impact" stay as written.

    python scripts/companion/gen_k11.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

cc, lib = c.cc, c.lib
HEAD = r"^EVENT \d{3}\s+-\s+"
V = c.VILLAGER
T = c.text_only
MODERN = "rule 3 (2026-11-14): a modern-day thing in the words of people who never saw one"

FOLIAGE = {"roles": {"botanist": c.skilled(V, "Farming")},
           "eff": {"c": [c.skill("botanist", "Farming")], "d": [c.skill("botanist", "Research")]},
           "to": {"d": [T("the original plant is lost", "a plant, not a villager or the village's food")]},
           "sens": {}}
FLOWERS = {"roles": {"dye_maker": V, "naturalist": c.skilled(V, "Research")},
           "eff": {"a": [c.skill("naturalist", "Research")], "b": [c.skill("dye_maker", "Research")],
                   "d": [c.skill("dye_maker", "Research")]},
           "to": {"c": [T("the plant may set no seed", "a wild plant; no food or crop is lost")]},
           "sens": {}}


def an(word: str) -> str:
    return ("an " if word[:1].upper() in "AEIOU" else "a ") + word


def build(row: dict) -> dict:
    num = c.num_of(row)
    tpl = FOLIAGE if num <= 79 else FLOWERS
    h = c.heading_line(row, HEAD)
    title = re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    premise, note = h + 1, h + 10
    assert c.line(premise).startswith("Premise:"), row["id"]
    assert c.line(note).startswith("Context / follow-up:") and note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "Context / follow-up: the catalogue entry and designer notes, never shown"})
    fixes = {}
    m = re.search(r"discovers a ([AEIOU]\w+)", c.line(premise))
    if m:
        fixes[premise] = [(f"a {m.group(1)}", f"an {m.group(1)}")]
    sens = {}
    for i, k in enumerate("abcd"):
        out = h + 3 + 2 * i
        for b, a in tpl["sens"].get(k, []):
            assert b in c.line(out), (row["id"], k, b)
            sens.setdefault(out, []).append((b, a))
            ledger.append({"src": c.L(out), "kind": "sensitivity", "before": b, "after": a, "why": MODERN})

    def shown(n: int) -> str:
        with lib.use_source(lib.COMPANION_ID):
            p = cc.processed_line(n, {}, {n: fixes.get(n, []) + sens.get(n, [])})
        return p[:1].upper() + p[1:]

    choices, nodes = [], {}
    for i, k in enumerate("abcd"):
        lab, out = h + 2 + 2 * i, h + 3 + 2 * i
        assert c.line(lab).strip().startswith("CHOICE:") and c.line(out).strip().startswith("OUTCOME:"), (row["id"], k)
        choices.append({"label": shown(lab), "next": k, "src": c.L(lab)})
        nodes[k] = c.page(f"Answer {k.upper()}", shown(out), c.L(out), tpl["eff"].get(k, ()), tpl["to"].get(k, ()))
    text = shown(premise)
    q = {"type": "question", "name": "The premise", "text": text, "src": c.L(premise), "choices": choices}
    if num <= 79:
        sp = re.match(r"A botanist discovers an? (.+?) growing", text).group(1)
        desc = f"A botanist finds {an(sp)} whose leaves hold water well, but a neighboring one looks different."
    else:
        sp = re.match(r"Only one (.+?) is flowering", text).group(1)
        desc = f"Only one {sp} is in flower: a dye maker wants its petals, a naturalist its insect visitors."
    assert c.description_ok(desc), (row["id"], desc, len(desc))
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
           "requirement": {"min_eligible": len(tpl["roles"])}, "roles": tpl["roles"], "start": "premise",
           "nodes": {"premise": q, **nodes}}
    if m:
        doc["grammar_fixes"] = [{"src": c.L(premise), "before": f"a {m.group(1)}", "after": f"an {m.group(1)}"}]
    return doc


def main() -> int:
    rows = [r for r in c.rows("cat") if 57 <= c.num_of(r) <= 116]
    assert len(rows) == 60, len(rows)
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
