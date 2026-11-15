"""Chunk K3: write the Companion Anthology's Volume 1 Part 2, Everyday Life & Personality, events 061-100
(companion L1667-2015) and Part 5, Material Culture, Foodways, Community & Belief, events V001-V030 (L3320-3539),
as data/event_collection/companion/c5/c5b<NNN>_<slug>.json and c5ev<NNN>_<slug>.json, then format and check them.

PART 2 (design notes L1132-1140; the same shape as chunk K2's 001-060):
  EVENT 0NN - Title / <one-sentence scene> /
    TWO CHOICES: A-B or THREE CHOICES: A-C (the same labels in every such event), then POSSIBLE ENDINGS: two bullets;
    or  NO CHOICE - One possible ending is selected: two bullets  /  OPTIONAL CONTINUITY: (the same in all 100)
- No-choice events: one popup, the scene, then one of the two endings appended, equally likely.  Choice events: the
  scene is the question page with the source's own generic labels, each with its own src, all leading to the SAME
  ending branch ("Endings are alternatives", L1140).
- "TWO CHOICES:", "THREE CHOICES:", "POSSIBLE ENDINGS:" and "NO CHOICE - ..." are structural; "OPTIONAL CONTINUITY:"
  is a designer note.
- Effects: "For events with a child and a designated caregiver/guardian, grant that caregiver Parenting experience on
  every outcome" (L1137): the parent of 077 is cast parent_of the child and gains a small Parenting on both endings.
  "Effects should be subtle ... Many events need no mechanical reward" (L1135): nothing else.  An elder, mentor,
  master or adult who only talks with a child is not a designated caregiver (as K2).

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

V, G, CH, EL, TEEN = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN
YOUNG = {"kind": "villager", "min_age": 3, "max_age": 17}           # "a young villager" (as K2)
YOUNG_ADULT = {"kind": "villager", "min_age": 18, "max_age": 25}    # "a young adult"
BUILDER = c.skilled(V, "Building")
FARMER = c.skilled(V, "Farming")
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")                                  # a naturalist, a researcher

# ---- Part 2, 061-100 -------------------------------------------------------------------------------------------------
HEAD_B = r"^EVENT \d{3}\s+-\s+"

# num: ({role: spec}, [roles that gain Parenting on every ending], description, {ending 1-2 or 0 (scene): [text_only]})
B = {
    61: ({"rival1": V, "rival2": V}, [], "Two former rivals meet while gathering firewood.", {}),
    62: ({"young": YOUNG_ADULT}, [], "A young adult is trusted with a small but important duty.", {}),
    63: ({"villager": V}, [], "A villager receives advice they did not ask for.", {}),
    64: ({"villager": V}, [], "A villager visits a quiet spot where they often go to think.", {}),
    65: ({"villager": G}, [], "A villager notices a silver strand in their hair.", {}),
    66: ({"elder": EL}, [], "An elder rests beside a tree they remember from childhood.", {}),
    67: ({"farmer": FARMER}, [], "A farmer notices the days growing subtly shorter.", {}),
    68: ({"friend1": V, "friend2": V}, [], "Two busy friends find a few minutes to talk between chores.", {}),
    69: ({"villager": V}, [], "A villager becomes emotional while hearing an old song.", {}),
    70: ({"young": YOUNG}, [], "A young villager worries they will never become a master at their craft.", {}),
    71: ({"villager": V}, [], "A talented villager worries that succeeding will change how others treat them.", {}),
    72: ({"friend1": V, "friend2": V}, [], "Two friends invent a greeting they use only with each other.", {}),
    73: ({"villager": V}, [], "A villager leaves fresh flowers beside the hospital doorway.", {}),
    74: ({"villager1": V, "villager2": V}, [], "The last two villagers at a gathering watch the fire burn low.",
         {0: [c.text_only("die", "the fire dies down; nobody dies")]}),
    75: ({"villager": V}, [], "A villager understands a problem only after stepping away from it.", {}),
    76: ({"traveler": V}, [], "A traveler wonders whether home is a place or the people who welcome them.", {}),
    77: ({"child": CH, "parent": c.related(G, "parent_of", "child")}, ["parent"],
         "A parent tells a child the names of familiar constellations.", {}),
    78: ({"villager": V, "friend": V}, [], "A villager notices a friend has been unusually quiet.", {}),
    79: ({"villager": V, "friend": V}, [], "A villager realizes winning an argument cost them a friend's feelings.", {}),
    80: ({"villager": V, "other": V}, [], "Someone receives forgiveness for an old offense they have long regretted.", {}),
    81: ({"villager": V}, [], "A villager looks around at familiar huts, trees and neighbors and suddenly feels grateful.", {}),
    82: ({"child": CH, "adult": G}, [], "A child shows an adult a drawing of the entire village.", {}),
    83: ({"young": YOUNG, "elder": EL}, [], "A young villager jokes about what they will be like when they are old.", {}),
    84: ({"villager": V, "friend": V}, [], "A villager asks a friend how to choose between two good opportunities.", {}),
    85: ({"villager": V}, [], "A villager wakes from a vivid dream about an unfamiliar shore.", {}),
    86: ({"dancer": V}, [], "Someone begins a gentle dance beside the communal fire.", {}),
    87: ({"apprentice": V, "mentor": G}, [], "An apprentice brings their mentor a handmade gift.", {}),
    88: ({"child": CH, "elder": EL}, [], "A child asks an elder why their hands look so different.", {}),
    89: ({"villager1": V, "villager2": V}, [], "Two villagers quietly discuss whether the spirits hear their prayers.", {}),
    90: ({"villager": V}, [], "A villager says aloud the name of someone who died long ago.", {}),
    91: ({"explorer": V}, [], "An explorer promises to tell the children what lies beyond the next ridge.", {}),
    92: ({"traveler": V}, [], "A tired traveler returns to the village at dusk.",
         {1: [c.text_only("food", "friends greet a traveler with a meal; the village's food is unchanged")]}),
    93: ({"villager": V}, [], "A timid villager finally speaks during a communal discussion.", {}),
    94: ({"relative1": V, "relative2": V}, [], "Two relatives who have avoided each other sit together at a festival.", {}),
    95: ({"villager": V}, [], "A villager marks a personal milestone nobody else knew about.",
         {1: [c.text_only("celebration", "a friend joins one villager's private celebration, not the village's (rule 7)")]}),
    96: ({"villager": V}, [], "A villager decides not to rush through breakfast for once.", {}),
    97: ({"child": CH, "elder": EL}, [], "A child retells an elder's tale with outrageous embellishments.", {}),
    98: ({"master": G, "child": CH}, [], "A master craftsperson allows a child to try a simple safe task.", {}),
    99: ({"child": CH, "adult": G}, [],
         "A child asks why people grow old, why stars shine and where dreams come from, all at once.", {}),
    100: ({"villager": V, "friend": V}, [], "A villager thanks a friend who sat beside them during a difficult time.", {}),
}


def build_b(row: dict) -> dict:
    num = c.num_of(row)
    roles, carers, desc, notes = B[num]
    assert c.description_ok(desc), (num, desc)
    h = c.heading_line(row, HEAD_B)
    title = c.re.split(HEAD_B, c.line(h), maxsplit=1)[1].strip()
    scene = h + 1
    body = {n: c.line(n).strip() for n in range(h + 2, row["lines"][1] + 1)}
    marker = h + 2
    head = body[marker]
    cont = next(n for n, s in body.items() if s.startswith("OPTIONAL CONTINUITY:"))
    ledger = []
    if head.startswith("NO CHOICE"):
        labels, ends_at = [], marker
        ledger.append({"src": c.L(marker), "kind": "structural", "why": "no choice: one ending is drawn"})
    else:
        assert head in ("TWO CHOICES:", "THREE CHOICES:"), (row["id"], head)
        ends_at = next(n for n, s in body.items() if s == "POSSIBLE ENDINGS:")
        labels = [n for n in range(marker + 1, ends_at) if body[n]]
        assert len(labels) == (2 if head.startswith("TWO") else 3), row["id"]
        ledger += [{"src": c.L(marker), "kind": "structural", "why": "the choices' heading"},
                   {"src": c.L(ends_at), "kind": "structural", "why": "the endings' heading: one is drawn"}]
    endings = [n for n in range(ends_at + 1, cont) if body[n]]
    assert len(endings) == 2 and all(body[n].startswith("•") for n in endings), row["id"]
    ledger.append({"src": c.L(cont), "kind": "note",
                   "why": "OPTIONAL CONTINUITY: a designer note on memory and callbacks, never shown (rule 9)"})
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
    rows_b = [r for r in c.rows("c5b") if c.num_of(r) in B]
    rows_e = [r for r in c.rows("c5ev") if c.num_of(r) in E]
    assert len(rows_b) == len(B) == 40 and len(rows_e) == len(E) == 30, (len(rows_b), len(rows_e))
    docs = [(r["section"], r["id"], build_b(r)) for r in rows_b]
    docs += [(r["section"], r["id"], build_e(r)) for r in rows_e]
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
