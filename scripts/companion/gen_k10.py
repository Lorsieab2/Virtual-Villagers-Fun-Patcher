"""Chunk K10: write The Living Catalogue's fish bodies and fins, events 001-056 (companion L7109-7779), as
data/event_collection/companion/cat/cat<NNN>_<slug>.json, then format and check them.

THE SOURCE'S FORMAT (L7107 "CHOICES ARE EXCLUSIVE; EACH HAS A DISTINCT OUTCOME"; 11 lines per event):
  EVENT NNN - Title / Premise: / 4 x (CHOICE: label / OUTCOME: text) / Context / follow-up: (a designer note)
- A true 1:1 choice: the premise is the question page with the four labels, and each label leads to its own answer
  page.  "Premise:", "CHOICE:" and "OUTCOME:" are structural markers; "Context / follow-up:" is a designer note.
- Two templates with the species name swapped (scratchpad comp_cat.py): 001-028 "A Record of the <Body>" (five
  premise variants, the same choices and outcomes) and 029-056 "The <Fin> Fin Question" (one template).  The manifest
  puts them in the series cat_bodies and cat_fins: each series counts as ONE event in the rare roll.
- The species names are the Fish and Plant Tycoon names as Isolan species (the owner's choice), verbatim.

CASTING: the text names nobody (rule 10).  "A young naturalist" (001-028) is a villager 14-25 with some Research; the
second observer is a text figure.  "A fisher" and "a jeweler" (029-056) are villagers; the jeweler is cast only.

EFFECTS (V28 consequence rules; the owner 2026-11-14: hands-on study earns small Research):
- Bodies: B "Keep a living specimen briefly for observation" (the fish "reveals details") and C "Preserve a collected
  specimen" ("The record gains anatomical detail"): the naturalist's small Research.  A (a sketch from a distance)
  and D (waiting) are observation only: no effect.
- Fins: C "Examine a naturally deceased fish" ("The fin structure is clearer") and D "Capture a live fish to preserve
  it" ("A complete specimen improves comparison"): the fisher's small Research ("the villager records").  A and B
  (watching, sketching) no effect.
- Nobody is hurt: the fish that dies, is stressed or disappears is an animal (text only).

GRAMMAR (docs/event-collection/grammar-fixes.md, companion section): "believes its a <trait>" -> "believes its
<trait>" (22 body premises), "a Orange / a Oriental / a Angel" -> "an ..." (L7542, L7554, L7722).

    python scripts/companion/gen_k10.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

HEAD = r"^EVENT \d{3}\s+-\s+"
NATURALIST = c.skilled({"kind": "villager", "min_age": 14, "max_age": 25}, "Research")   # "A young naturalist"
T = c.text_only

# per template: the answers (a-d) whose hands-on study earns small Research, who gains it, and the animal words
BODY = {"research": ("b", "c"), "who": "naturalist",
        "to": {"b": [T("handling stresses it", "the fish is stressed, not a villager")],
               "c": [T("the fish dies", "an animal, not a villager")],
               "d": [T("The fish disappears for days", "an animal, not a villager; no one vanishes")]}}
FIN = {"research": ("c", "d"), "who": "fisher",
       "to": {"c": [T("a naturally deceased fish", "an animal found dead; no villager dies")],
              "d": [T("kills the animal", "an animal, not a villager")]}}


def article(word: str) -> str:
    return "an" if word[:1].upper() in "AEIOU" else "a"


def grammar_fix(n: int) -> dict | None:
    s = c.line(n)
    m = re.search(r"believes its a ", s)
    if m:
        return {"src": c.L(n), "before": "believes its a", "after": "believes its"}
    m = re.search(r"that a ([AEIOU]\w+)", s)
    if m:
        return {"src": c.L(n), "before": f"that a {m.group(1)}", "after": f"that an {m.group(1)}"}
    return None


def build(row: dict) -> dict:
    num = c.num_of(row)
    tpl = BODY if num <= 28 else FIN
    h = c.heading_line(row, HEAD)
    title = re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    premise, note = h + 1, h + 10
    assert c.line(premise).startswith("Premise:"), row["id"]
    assert c.line(note).startswith("Context / follow-up:") and note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "Context / follow-up: the catalogue entry and designer notes, never shown"})
    fix = grammar_fix(premise)
    fixes = {premise: [(fix["before"], fix["after"])]} if fix else {}
    with c.lib.use_source(c.lib.COMPANION_ID):
        text = c.cc.processed_line(premise, {}, fixes)
    text = text[:1].upper() + text[1:]
    choices, nodes = [], {}
    for i, k in enumerate("abcd"):
        lab, out = h + 2 + 2 * i, h + 3 + 2 * i
        assert c.line(lab).strip().startswith("CHOICE:") and c.line(out).strip().startswith("OUTCOME:"), (row["id"], k)
        choices.append({"label": c.shown(lab), "next": k, "src": c.L(lab)})
        eff = [c.skill(tpl["who"], "Research")] if k in tpl["research"] else []
        nodes[k] = c.page(f"Answer {k.upper()}", c.shown(out), c.L(out), eff, tpl["to"].get(k, ()))
    q = {"type": "question", "name": "The premise", "text": text, "src": c.L(premise), "choices": choices}
    if num <= 28:
        m = re.match(r"A young naturalist observes an? (.+?) in (.+?) and believes", text)
        sp, place = m.group(1), m.group(2)
        roles = {"naturalist": NATURALIST}
        desc = f"A young naturalist observes {article(sp)} {sp} in {place}, but another observer disputes its fin shape."
    else:
        m = re.match(r"A fisher claims that an? (.+?) swims differently", text)
        sp = m.group(1)
        roles = {"fisher": c.VILLAGER, "jeweler": c.VILLAGER}
        desc = f"A fisher says {article(sp)} {sp} swims differently, and a jeweler wants its fin as a model for metalwork."
    assert c.description_ok(desc), (row["id"], desc)
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r != tpl["who"]]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
           "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "premise",
           "nodes": {"premise": q, **nodes}}
    if fix:
        doc["grammar_fixes"] = [fix]
    return doc


def main() -> int:
    rows = [r for r in c.rows("cat") if c.num_of(r) <= 56]
    assert len(rows) == 56, len(rows)
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
