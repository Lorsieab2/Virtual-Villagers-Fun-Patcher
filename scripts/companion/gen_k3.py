"""Chunk K3: write the Companion Anthology's Volume 1 Part 5, Material Culture, Foodways, Community & Belief,
events V001-V030 (companion L3320-3539), as data/event_collection/companion/c5/c5ev<NNN>_<slug>.json, then format
and check them.

PART 2 061-100 are rows of gen_c5b.py's table E (shared with chunk K2), not built here.

PART 5 (L3313-3317; V001-V050 "short encounters; each has two alternative outcomes"):
  group heading with a dash underline (above V001, V011, V021) / EVENT Vnnn - Title / SETUP: / OUTCOME A: /
  OUTCOME B: / CHOICE: Optional; use no-choice resolution when the situation is purely observational.
- Every event is observational: one popup, the setup, then one outcome appended, equally likely.  "CHOICE: Optional;
  ..." (the same in all 50) is a designer note.  The outcomes written as actions ("Make a special garment for a
  celebration.", V006, V007, V009: inventory Q-imperatives) are the owner's story lines and ship as written.
- Effects (the V28 consequence rules: only where the text clearly supports one, no reward inflation): a builder who
  does the building work the outcome names gains a small Building (V004 B, V009 A/B, V026 A); a naturalist or
  researcher who identifies, documents or compares gains a small Research (V013 A, V018 B, V029 B); "Stored food
  lasts longer" (V019 A) is a small food gain; "A child discovers a favorite vegetable" (V011 A) adds a like, in the
  game's own word (A New Home has no "vegetables": its vegetable is "turnips"; gap C1 write-around, a child with an
  "if" per game).  Nobody is harmed.

    python scripts/companion/gen_k3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

V, CH, EL, TEEN = c.VILLAGER, c.CHILD, c.ELDER, c.TEEN
BUILDER = c.skilled(V, "Building")
FARMER = c.skilled(V, "Farming")
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")                                  # a naturalist, a researcher

# ---- Part 5, V001-V030 -----------------------------------------------------------------------------------------------
HEAD_E = r"^EVENT V\d{3}\s+-\s+"


def bld(role: str) -> dict:
    return c.skill(role, "Building")


def res(role: str) -> dict:
    return c.skill(role, "Research")


FOOD_SMALL = {"do": "food", "size": "small", "scaled": True}
# A New Home's own word for a vegetable is "turnips"; the other four have "vegetables" (gap C1 write-around).
LIKE_VEG = {1: "turnips", "*": "vegetables"}

# num: ({role: spec}, description, {outcome 1-2: [effects]}, {outcome 1-2 or 0 (setup): [text_only]})
E = {
    1: ({"weaver": V, "apprentice": TEEN}, "A weaver works pandanus, reeds and dyed fibers into a pattern their grandparents used.", {}, {}),
    2: ({"maker1": V, "maker2": V}, "Two craftspeople compete to weave baskets that keep stored grain dry.", {}, {}),
    3: ({"dollmaker": V, "child": CH}, "A dollmaker carves a driftwood face and stitches a body from scrap cloth.", {}, {}),
    4: ({"toymaker": V, "builder": BUILDER}, "A toymaker creates a little fish that wiggles when pulled by a cord.",
        {2: [bld("builder")]}, {}),
    5: ({"villager": V}, "A household decorates its hut with shells, painted bark, woven mats and keepsakes.", {}, {}),
    6: ({"tailor": V}, "A tailor has one beautiful piece of cloth and three requests for it.", {},
        {1: [c.text_only("celebration", "a garment for a celebration; the village does not celebrate now (rule 7)")]}),
    7: ({"carver": V}, "A woodcarver accidentally removes an important feature from a ceremonial figure.", {}, {}),
    8: ({"villager": V}, "A new household weaves a mat that carries a symbol of hospitality.", {}, {}),
    9: ({"builder": BUILDER}, "A building team finds a roof that sheds rain beautifully but traps heat.",
        {1: [bld("builder")], 2: [bld("builder")]}, {}),
    10: ({"villager": V, "child": CH}, "A sewing needle passes from family to family and gains a history of its own.", {}, {}),
    11: ({"cook": V, "child": CH}, "Cooks prepare a meal of breadfruit, taro, greens, squash, coconut, beans and herbs.",
         {}, {}),
    12: ({"gatherer": V, "healer": HEALER}, "Gatherers return with clams, mussels, oysters, limpets and sea snails.", {}, {}),
    13: ({"fisher": V, "naturalist": SCHOLAR}, "A catch includes reef fish, squid, octopus and an unfamiliar crustacean.",
         {1: [res("naturalist")]}, {}),
    14: ({"cook": V, "elder": EL}, "A cook proposes using eggs from several locally known laying creatures.", {}, {}),
    15: ({"villager": V}, "A household prepares a communal meal from a pig raised for food.", {},
          {0: [c.text_only("food", "a household's meal from its own pig; the village's food is unchanged")]}),
    16: ({"farmer": FARMER}, "Farmers test unfamiliar edible grains and seeds in porridge, flat cakes and toasted snacks.", {}, {}),
    17: ({"villager": V}, "A family arranges papaya, banana, guava, mango, citrus, coconut and other fruits.", {}, {}),
    18: ({"diver": V, "naturalist": SCHOLAR}, "Divers bring back edible seaweed while leaving fragile reef habitats intact.",
         {2: [res("naturalist")]}, {}),
    19: ({"fisher": V, "cook": V}, "Fishers and cooks debate drying, salting and smoking a surplus catch.",
         {1: [FOOD_SMALL]},
         {2: [c.text_only("food", "the apprentice learns a lesson about spoiled food; no stores are named as lost")]}),
    20: ({"cook": V}, "A cook combines coconut cream, roasted seeds, fruit and a pinch of sea salt.", {}, {}),
    21: ({"swimmer": V, "apprentice": V}, "A confident swimmer helps a nervous apprentice practice in shallow water.", {}, {}),
    22: ({"diver": V}, "A diver finds an unusual object beneath a shallow reef ledge.", {}, {}),
    23: ({"diver1": V, "diver2": V}, "Divers disagree about collecting beautiful living coral.", {}, {}),
    24: ({"boatbuilder": V}, "A boatbuilder proposes a canoe that can travel in either direction without turning.", {}, {}),
    25: ({"sailor": V}, "Several crews compare woven-mat sails, cloth sails and different rigging.", {}, {}),
    26: ({"builder": BUILDER}, "Families compare shade, breezes, raised floors and roofs during a heat wave.",
         {1: [bld("builder")]}, {}),
    27: ({"villager": V, "tailor": V}, "An unusually chilly night catches villagers unprepared.", {}, {}),
    28: ({"elder": EL, "child": CH}, "An elder teaches children to recognize changing wind, clouds and surf.", {}, {}),
    29: ({"builder": V, "researcher": SCHOLAR}, "After seasonal flooding, builders mark the highest waterline on a stone.",
         {2: [res("researcher")]}, {}),
    30: ({"paddler": V}, "A canoe crew realizes one paddle has gone missing during a short voyage.", {},
         {0: [c.text_only("vanished", "a paddle goes missing; no villager vanishes")]}),
}


def build_e(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, effects, notes = E[num]
    assert c.description_ok(desc), (num, desc)
    h = c.heading_line(row, HEAD_E)
    title = c.re.split(HEAD_E, c.line(h), maxsplit=1)[1].strip()
    setup, oa, ob, note = h + 1, h + 2, h + 3, h + 4
    assert c.line(setup).startswith("SETUP:") and c.line(oa).startswith("OUTCOME A:"), row["id"]
    assert c.line(ob).startswith("OUTCOME B:") and c.line(note).startswith("CHOICE: Optional;"), row["id"]
    assert note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "CHOICE: Optional; a designer note: the event is observational, one outcome is drawn"})
    nodes: dict = {"setup": {"name": "The setup", "text": c.shown(setup), "src": c.L(setup),
                             "children": [{"next": "e1"}, {"next": "e2"}]}}
    if notes.get(0):
        nodes["setup"]["text_only"] = c.with_src(notes[0], c.L(setup))
    used = set()
    for k, n in enumerate((oa, ob), 1):
        eff = effects.get(k, [])
        for e in eff:
            if "role" in e:
                used.add(e["role"])
        nodes[f"e{k}"] = c.page(f"Outcome {chr(64 + k)}", c.shown(n), c.L(n), eff, notes.get(k, ()), append=True)
    if num == 11:
        # "A child discovers a favorite vegetable." -- a like in the game's own word, one page per word
        base = nodes.pop("e1")
        for key, word in LIKE_VEG.items():
            nid = "e1_vv1" if key == 1 else "e1"
            nodes[nid] = dict(base, effects=c.with_src(
                [{"do": "preference", "role": "child", "list": "likes", "preference": word}], c.L(oa)))
        nodes["setup"]["children"][0] = {"next": "e1_vv1", "if": {"game": [1]}, "else": "e1"}
        used.add("child")
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "setup", "nodes": nodes}


def main() -> int:
    rows_e = [r for r in c.rows("c5ev") if c.num_of(r) in E]
    assert len(rows_e) == len(E) == 30, len(rows_e)
    return c.write_and_check([(r["section"], r["id"], build_e(r)) for r in rows_e])


if __name__ == "__main__":
    sys.exit(main())
