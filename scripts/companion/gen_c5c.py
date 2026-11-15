"""Write the Companion Anthology's Volume 1 Part 3, Small Lives, Deep Roots, events 001-030 (companion L2041-2408),
as data/event_collection/companion/c5/c5c<NNN>_<slug>.json, then format and check them.

The source's format (L2035: "Each event uses a single randomized ending; where choices appear, they are optional
prompts"):
  SMALL LIFE EVENT 0NN - Title / <one-sentence scene> / NO CHOICE.  (or CHOICES: with two labels of its own)
  / POSSIBLE ENDINGS (select one): two bullets / TONE: quiet; no large reward required. ... (the same in all 50)

How it maps (docs/event-collection/companion-authoring.md):
- No-choice events: one popup -- the scene, then one of the two endings appended to it, equally likely (the V27
  shape).  Choice events: the scene is the question page with the source's two labels, and both lead to the same
  ending branch (the choices are "optional prompts", not routes).
- "NO CHOICE.", "POSSIBLE ENDINGS (select one):", "CHOICES:" are structural; "TONE:" is a designer note.
- Effects: the part's rule (L2038) "Parenting experience is awarded to designated caregivers in every child-related
  outcome" -- where the text names a child's parent (003, 009, 025), that parent is cast (parent_of the child) and
  gains a small Parenting on BOTH endings.  The tone is "no large reward required": no other effect.  Words the
  effects table reads that change nothing ("death", "die", "food", "celebrates") are text_only with the reason.
- Kinship the text states is cast as kinship (cie-v6-binary.md 21): two siblings (002), a father and his child (003),
  a parent and their grown child (004), a parent and their child (009, 025).
- Deceased loved ones (010, 013, 023, 027, 028) stay generic text: no role can name a real dead relative yet (gap C3).

    python scripts/companion/gen_c5c.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

HEAD = r"^SMALL LIFE EVENT \d{3}\s+-\s+"
V, G, CH, EL = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER
GROWN_CHILD = c.GROWN

# num: ({role: spec}, [roles that gain Parenting on every ending], description, {ending 1-2 or 0 (scene): [text_only]})
E = {
    1: ({"cook": V}, [], "A cook sets out two bowls before remembering that only one person is coming to supper.", {}),
    2: ({"sibling1": c.ANY_AGE, "sibling2": c.related(c.ANY_AGE, "sibling_of", "sibling1")}, [],
        "Two siblings who argued shelter beneath the same broad leaf: let them speak first, or give them time.", {}),
    3: ({"child": CH, "father": c.related(c.sexed(G, "male"), "parent_of", "child")}, ["father"],
        "A father tries to braid his child's hair and produces a spectacular knot.", {}),
    4: ({"grown": GROWN_CHILD, "parent": c.related(G, "parent_of", "grown")}, [],
        "A parent watches their grown child move into a hut of their own.", {}),
    5: ({"writer": V}, [], "A villager writes to someone they can no longer speak to: keep it private, or read it quietly.", {}),
    6: ({"friend1": V, "friend2": V}, [], "Two villagers realize their closest friends have never met.", {}),
    7: ({"child": CH}, [], "Children hold a solemn ceremony for a dead beetle.",
        {2: [c.text_only("death", "the children ask about death; nobody dies")]}),
    8: ({"villager": V}, [], "A villager wakes in an unusually cheerful mood.", {}),
    9: ({"child": CH, "parent": c.related(G, "parent_of", "child")}, ["parent"],
        "A child presents a collection of forty-seven nearly identical stones.", {}),
    10: ({"villager": V}, [], "Someone regrets an abrupt goodbye to a loved one who died: tell a friend, or remember alone.", {}),
    11: ({"villager": V}, [], "An old carving holds the name of a villager no one remembers.", {}),
    12: ({"novice": V}, [], "A novice finally manages a simple task that has defeated them for weeks.", {}),
    13: ({"villager": V}, [], "A villager catches themselves laughing exactly like a deceased relative.", {}),
    14: ({"scholar": V, "fisher": V}, [], "A shy scholar and a boisterous fisher end up sitting together at a festival.", {}),
    15: ({"villager": V}, [], "An unused hammock sways in the evening breeze.", {}),
    16: ({"friend1": V, "friend2": V}, [], "Two friends each insist the other should eat the last ripe mango.", {}),
    17: ({"builder": c.skilled(V, "Building")}, [], "A respected builder admits being afraid of deep water.", {}),
    18: ({"watcher": V}, [], "A villager sits awake beside a sick relative while the village sleeps.", {}),
    19: ({"villager": V}, [], "A villager hears a melody they thought they had forgotten.", {}),
    20: ({"child": CH}, [], "A child proudly shows a gap where a tooth used to be.",
         {1: [c.text_only("celebrates", "the household's own little celebration, not the village's (rule 7)")]}),
    21: ({"neighbor1": V, "neighbor2": V}, [], "Two neighbors secretly compete to keep the tidier doorstep.", {}),
    22: ({"elder": EL}, [], "An elderly villager says the sunset looks just like one from their childhood.", {}),
    23: ({"villager": V}, [], "A family tries to recreate a dish once made by someone who has died.", {}),
    24: ({"newcomer": V, "friend": V}, [], "A newcomer is surprised when another villager saves them a place by the fire.", {}),
    25: ({"child": CH, "parent": c.related(G, "parent_of", "child")}, ["parent"],
         "A child discovers that last season's sandals no longer fit.", {}),
    26: ({"villager": V, "elder": EL}, [],
         "A villager wants to ask an elder about the past: ask gently, or wait for a better moment.", {}),
    27: ({"villager": V}, [], "Someone asks the ocean why a loved one had to die.",
         {0: [c.text_only("die", "a loved one's death in the past; nobody dies now")]}),
    28: ({"villager": V}, [], "A villager quietly marks an anniversary nobody else knows about.",
         {2: [c.text_only("food", "a favorite food eaten in remembrance; no food is gained or lost")]}),
    29: ({"friend1": V, "friend2": V}, [],
         "Two friends talk about a mistake that strained their friendship: apologize, or ask what would help.", {}),
    30: ({"villager": V, "other": V}, [], "A villager offers an apology, but the other person is not ready.", {}),
}


def build(row: dict) -> dict:
    num = c.num_of(row)
    roles, carers, desc, notes = E[num]
    assert c.description_ok(desc), (num, desc)
    h = c.heading_line(row, HEAD)
    title = c.re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    scene = h + 1
    body = {n: c.line(n).strip() for n in range(h + 2, row["lines"][1] + 1)}
    marker = next(n for n, s in body.items() if s in ("NO CHOICE.", "CHOICES:"))
    ends_at = next(n for n, s in body.items() if s == "POSSIBLE ENDINGS (select one):")
    endings = [n for n in range(ends_at + 1, ends_at + 3)]
    tone = next(n for n, s in body.items() if s.startswith("TONE:"))
    labels = [n for n in range(marker + 1, ends_at) if body[n]] if body[marker] == "CHOICES:" else []
    assert len(endings) == 2 and all(body[n].startswith("•") for n in endings), row["id"]
    ledger = [{"src": c.L(marker), "kind": "structural",
               "why": "no choice: one ending is drawn" if not labels else "the choices' heading"},
              {"src": c.L(ends_at), "kind": "structural", "why": "the endings' heading: one is drawn"},
              {"src": c.L(tone), "kind": "note", "why": "TONE: a designer note on the tone and rewards, never shown"}]
    nodes: dict = {}
    if labels:
        nodes["scene"] = {"type": "question", "name": "The scene", "text": c.shown(scene), "src": c.L(scene),
                          "choices": [{"label": c.shown(n), "next": "ending", "src": c.L(n)} for n in labels]}
        nodes["ending"] = {"type": "branch", "children": [{"next": "e1"}, {"next": "e2"}]}
    else:
        nodes["scene"] = {"name": "The scene", "text": c.shown(scene), "src": c.L(scene),
                          "children": [{"next": "e1"}, {"next": "e2"}]}
    if notes.get(0):
        nodes["scene"]["text_only"] = c.with_src(notes[0], c.L(scene))
    for k, n in enumerate(endings, 1):
        nodes[f"e{k}"] = c.page(f"Ending {k}", c.shown(n), c.L(n), [c.parenting(r) for r in carers],
                                notes.get(k, ()), append=not labels)
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in carers]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "scene", "nodes": nodes}


def main() -> int:
    rows = [r for r in c.rows("c5c") if c.num_of(r) <= 30]
    assert len(rows) == len(E) == 30
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
