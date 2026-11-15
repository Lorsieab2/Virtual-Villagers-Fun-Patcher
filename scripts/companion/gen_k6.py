"""Chunk K6: write the Companion Anthology's The Lives Between Legends events 061-120 (companion L4593-5390) as
data/event_collection/companion/lbl/lbl<NNN>_<slug>.json, then format and check them.  Chunk K5's gen_k5.py builds
LBL 001-060 the same way (same folder, separate generator); this file copies its approach.

THE LIVES BETWEEN LEGENDS (engine rules L3779-3787):
  group heading between separator lines / EVENT NNN - Title / TRIGGER: (the same in all 120) / SCENE: /
  PLAYER RESPONSE A-C (the same three in all 120) / WEIGHTED OUTCOME 1-3: / PERSISTENCE: / EFFECTS: (the same in all).
- The scene is the question page; the three responses are the source's own labels, each with its own src, and all
  lead to the SAME outcome branch (L3782: "The branches are not necessarily tied one-to-one to choices").  No odds are
  given: the outcomes are equal, except a disappearance (rare, 5 against 20: 073's missing explorer).  TRIGGER,
  PERSISTENCE and EFFECTS are designer notes (rule 9: memories and callbacks).
- Minor setbacks (073's dive injury, 082's injured teen) keep the normal weight: collection_check's chance rule has no
  "occasional" weight yet (rare 5, very rare 2, exceptionally rare 1 only), so they stay equal (a lead TODO).
- Casting (the lead's decisions): elders 55+; "a child" 3-13; "a teen" 14-17; a sibling the text names is a relation
  (064).  "A family member" (105) has no relation kind: cast by age, text only.  Genders are random (L3780).
  Strangers the text names (083's unfamiliar villager, 119's child from a rival community, 074's raft owner) are
  text: nobody of the village is cast as them.
- 086 "The Unpopular Chief": the scene says "a competent leader" (no "Chief" in the text to make {@chief}); the title
  has a title variant, "The Unpopular Leader" outside The Secret City (an OPEN owner question in
  owner-title-changes.md).
- Effects (the V28 consequence rules, only on an outcome whose text supports it):
  hands-on work earns a small skill in the game skill it is: 061 nursing the seabird (Healing, the scene: every
  outcome), 064 documenting insect life cycles (Research), 067 the naturalist's identification (Research), 068 the
  careful study (Research) and the pest discovery (Farming), 069 the healer's check (Healing), 070 learning to
  identify occupied shells (Research), 073 the careful survey (Research), 076 the mapping expedition (Research),
  084 the translator (Research), 089 "gain Research experience" and the apprentice's discovery (Research), 091 the
  repair and the improved design (Building), 096 the night repairs (Building), 097 and 104 the inventions (Building,
  the scene), 103 the new clothesline (Building), 114 the census clerk and 120 the historian (Research, the scene),
  116 the healer's records (Healing), 117 the barriers (Building) and the habitat plan (Research);
  caregiving earns a small Parenting: 119's family that shelters a child;
  harm: 073 the dive injury (minor) and the explorer who disappears (vanish, rare: missing is not dead), 082 the
  injured teen (minor);
  looks: 098 the dyed hair (appearance, head random: outcomes 1 and 3), 099 the crooked garment that starts a trend
  (body random on its wearer);
  116 the patient who improves (a small health gain, the scene: every outcome);
  105 the neighbours' impromptu celebration (celebrate, all) and the stored meal (food, small).
  Everything else is text: animals (none is a villager), councils, policies, trade, reputations, elections and
  traditions (rule 7), music, tailoring and crafts no game has as a skill (rule 8), trust, rivalries and memories
  (rule 9).  No role uses protected "allow".

    python scripts/companion/gen_k6.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

V, G, CH, EL, TEEN = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN
YOUNG = {"kind": "villager", "min_age": 3, "max_age": 17}           # "a young villager", a sibling of a child
HEALER = c.skilled(V, "Healing")
BUILDER = c.skilled(V, "Building")
FARMER = c.skilled(V, "Farming")
SCHOLAR = c.skilled(V, "Research")                                  # a researcher, naturalist, historian, clerk
T = c.text_only
MINOR = (-30, -10)                                                  # a minor injury (companion-authoring.md 6)
RARE = (5, "rare")


def hurt(role: str) -> dict:
    return {"do": "health_change", "role": role, "min": MINOR[0], "max": MINOR[1]}


def res(role: str) -> dict:
    return c.skill(role, "Research")


def bld(role: str) -> dict:
    return c.skill(role, "Building")


def heal(role: str) -> dict:
    return c.skill(role, "Healing")


def look(role: str, part: str) -> dict:
    return {"do": "appearance", "role": role, part: "random"}


ANIMAL = "an animal, not a villager: nobody of the village is affected"

# num: ({role: spec}, description, opts)
# opts: eff {k: [effects]}, eff_scene [effects made on every outcome, src the scene line],
#       to {k or 0 (the scene): [text_only]}, w {k: (weight, rarity)}, title_variants [..]
L_ = {
    61: ({"child": CH}, "A child cares for an injured seabird until it can fly.",
         {"eff_scene": [heal("child")], "to": {0: [T("injured", "the seabird is injured, " + ANIMAL)]}}),
    62: ({"diver": V}, "A diver keeps losing small objects to a curious octopus.",
         {"to": {3: [T("disappears", "the octopus disappears, " + ANIMAL)]}}),
    63: ({"villager": V, "friend": V}, "A villager becomes attached to a particularly aggressive crab.",
         {"to": {2: [T("pinches", "a crab's pinch smarts; no injury is told")]}}),
    64: ({"child": CH, "sibling": c.related(YOUNG, "sibling_of", "child")},
         "A child watches a caterpillar transform into a butterfly.", {"eff": {2: [res("child")]}}),
    65: ({"villager": V}, "A villager finds a young pig alone near the forest.", {}),
    66: ({"child": CH}, "A child names a colorful fish in a tidal pool.",
         {"to": {2: [T("vanishes", "the fish vanishes, " + ANIMAL)]}}),
    67: ({"villager": V, "naturalist": SCHOLAR}, "A villager discovers an unfamiliar egg near a path.",
         {"eff": {2: [res("naturalist")]}, "to": {3: [T("disappears", "the egg disappears; nobody is affected")]}}),
    68: ({"apprentice": V, "villager": V}, "An apprentice finds a remarkable insect in the orchard.",
         {"eff": {1: [res("apprentice")], 3: [c.skill("apprentice", "Farming")]}}),
    69: ({"villager": V, "healer": HEALER}, "A wild creature begins following a villager home.",
         {"eff": {2: [heal("healer")]}}),
    70: ({"villager": V, "child": CH}, "A villager takes a beautiful shell that turns out to be occupied.",
         {"eff": {2: [res("villager")]}}),
    71: ({"villager": V}, "Birdsong and insect noise suddenly vanish from a familiar grove.",
         {"to": {0: [T("vanish", "the grove's sounds fall silent; nobody disappears")]}}),
    72: ({"builder1": BUILDER, "builder2": BUILDER}, "Builders find a nest in a tree marked for cutting.", {}),
    73: ({"explorer": V}, "A reckless villager tries to prove an ancient pool has no bottom.",
         {"eff": {1: [res("explorer")], 2: [hurt("explorer")], 3: [{"do": "vanish", "role": "explorer"}]},
          "w": {3: RARE},
          "to": {3: [T("disappears", "missing is not dead (L3784): the explorer vanishes, no death and no grave; "
                                     "the search is text")]}}),
    74: ({"villager": V}, "A damaged raft washes ashore with no passengers.",
         {"to": {2: [T("missing villager", "a past disappearance; nobody vanishes now")]}}),
    75: ({"watchkeeper": V, "colleague": V}, "A watchkeeper neglects the signal fire before a storm.",
         {"to": {2: [T("consequences", "rule 7: the watchkeeper's consequences are told only")]}}),
    76: ({"villager": V}, "Villagers hear rhythmic noises from a cave.", {"eff": {3: [res("villager")]}}),
    77: ({"villager": V}, "A villager follows footprints that end at the water.", {}),
    78: ({"villager": V}, "A villager predicts disaster after a vivid dream.", {}),
    79: ({"explorer1": V, "explorer2": V}, "Explorers discover signs of people living beyond familiar territory.",
         {"to": {1: [T("trade", "rule 7: trade is told only")]}}),
    80: ({"builder": BUILDER}, "A builder discovers an old passage beneath a hut.",
         {"to": {2: [T("unstable", "the old passage is closed; no building is damaged")]}}),
    81: ({"villager": V}, "A necklace is found near a dangerous cliff.",
         {"to": {2: [T("missing person", "a past disappearance; nobody vanishes now")]}}),
    82: ({"teen": TEEN, "friend": V}, "A teen attempts to recreate a legendary feat to win admiration.",
         {"eff": {3: [hurt("teen")]}}),
    83: ({"villager": V}, "An exhausted stranger appears at the shore at dawn.", {}),
    84: ({"villager": V, "translator": SCHOLAR}, "A drifting canoe contains a carved wooden message.",
         {"eff": {1: [res("translator")]}}),
    85: ({"researcher": SCHOLAR, "apprentice": V, "mediator": V},
         "A senior researcher takes credit for an apprentice's observation.",
         {"to": {1: [T("recognition", "rule 7: recognition is a reputation, told only")]}}),
    86: ({"leader": G}, "A competent leader is disliked for a harsh manner.",
         {"to": {0: [T("disliked", "the village's opinion of the leader, no game preference (rule 7)")],
                 2: [T("a different leader", "rule 7: leadership changes are told only")]},
          "title_variants": [{"if": {"game": [1, 2, 4, 5]}, "title": "The Unpopular Leader"}]}),
    87: ({"prankster": V, "friend": V}, "A notorious prankster reports a real danger.", {}),
    88: ({"expert": V, "leader": G, "colleague": V}, "A soft-spoken villager notices a flaw in a major project.", {}),
    89: ({"scientist": SCHOLAR, "apprentice": V}, "A scientist's public demonstration goes wrong.",
         {"eff": {1: [res("scientist")], 3: [res("apprentice")]}}),
    90: ({"healer": HEALER, "colleague": V}, "A healer is exhausted after several difficult cases.",
         {"to": {3: [T("a minor mistake", "nobody is said to be hurt by the mistake")]}}),
    91: ({"worker": V, "colleague": V, "craftsperson": V}, "A careless worker damages a shared tool.",
         {"eff": {1: [bld("worker")], 3: [bld("craftsperson")]}}),
    92: ({"candidate1": V, "candidate2": V}, "Two capable villagers seek the same leadership role.",
         {"to": {1: [T("council", "rule 7: councils and appointments are told only")]}}),
    93: ({"master": G, "apprentice": V}, "A master is assigned an apprentice they did not request.", {}),
    94: ({"worker1": V, "worker2": V, "leader": G, "elder": EL}, "Several villagers refuse a dangerous assignment.",
         {"to": {0: [T("strike", "rule 7: a strike is told only")]}}),
    95: ({"villager": V, "rival": V}, "A villager known as cowardly acts bravely during an emergency.", {}),
    96: ({"helper": V, "helper2": V}, "Supplies are mysteriously repaired each night.",
         {"eff": {1: [bld("helper")], 2: [bld("helper"), bld("helper2")], 3: [bld("helper")]}}),
    97: ({"inventor": V}, "An inventor builds a device to crack coconuts.",
         {"eff_scene": [bld("inventor")], "to": {3: [T("banned", "rule 7: bans are told only")]}}),
    98: ({"dyer": V, "volunteer": V}, "A dyer tests a new pigment on a willing volunteer.",
         {"eff": {1: [look("volunteer", "head")], 3: [look("volunteer", "head")]},
          "to": {2: [T("fades", "rule 9: a dye that fades is a passing look; the head is not changed")]}}),
    99: ({"tailor": V, "wearer": V}, "A tailor accidentally sews a garment asymmetrically.",
         {"eff": {1: [look("wearer", "body")]}}),
    100: ({"musician": V, "teacher": V}, "A talentless musician insists on performing at every feast.",
          {"to": {2: [T("improve", "rule 8: music is no game skill")]}}),
    101: ({"cook1": V, "cook2": V}, "Two cooks argue over the proper way to roast breadfruit.",
          {"to": {1: [T("contest", "rule 7: contests are told only")]}}),
    102: ({"villager": V, "prankster": V}, "A villager insists a pig has spoken a word.", {}),
    103: ({"villager1": V, "villager2": V}, "A gust scatters freshly washed clothing across the village.",
          {"eff": {3: [bld("villager1")]},
           "to": {2: [T("exchange outfits", "rule 9: a mix-up of washed clothes, not a lasting look")]}}),
    104: ({"craftsperson": V}, "A craftsperson creates an elaborate tool for a trivial task.",
          {"eff_scene": [bld("craftsperson")]}),
    105: ({"cook": V, "relative": V}, "A cook prepares an elaborate meal for the wrong date.",
          {"eff": {1: [c.celebrate_all()], 2: [{"do": "food", "size": "small", "scaled": True}]}}),
    106: ({"child1": CH, "child2": CH, "elder": EL}, "Children make instruments from shells, reeds and hollow wood.",
          {"to": {3: [T("teaches", "rule 8: music is no game skill")]}}),
    107: ({"villager": V, "friend": V}, "A villager spends hours searching for a sandal.",
          {"to": {1: [T("pet", "rule 9: no game has pets")]}}),
    108: ({"villager1": V, "villager2": V}, "Villagers compete to invent the least useful household object.",
          {"to": {2: [T("annual tradition", "rule 7: traditions are told only")]}}),
    109: ({"leader": G, "crew": V}, "A storm forces villagers to evacuate in limited boats.",
          {"to": {0: [T("storm", "the evacuation is told; nobody is hurt and nothing is damaged")]}}),
    110: ({"villager": V}, "Two communities disagree about a river crossing.",
          {"to": {2: [T("trade slows", "rule 7: trade is told only")]}}),
    111: ({"builder": BUILDER}, "Builders want timber from a revered grove.", {}),
    112: ({"child": CH, "elder": EL, "researcher": SCHOLAR}, "A child asks why spirits never answer clearly.", {}),
    113: ({"newcomer": V}, "A newcomer admits having made a serious mistake elsewhere.", {}),
    114: ({"clerk": SCHOLAR}, "A clerk attempts to record every villager and relationship.",
          {"eff_scene": [res("clerk")]}),
    115: ({"elder": EL, "villager": V}, "An elder wants to revive an old ritual.", {}),
    116: ({"patient": V, "healer": HEALER}, "A patient improves after both a ritual and medical treatment.",
          {"eff_scene": [{"do": "health_change", "role": "patient", "min": 10, "max": 30}],
           "eff": {2: [heal("healer")]}}),
    117: ({"farmer": FARMER, "naturalist": SCHOLAR}, "Farmers and naturalists disagree about animals eating crops.",
          {"eff": {1: [bld("farmer")], 2: [res("naturalist")]}}),
    118: ({"candidate1": G, "candidate2": G}, "Two villagers seek leadership with contrasting visions.",
          {"to": {0: [T("leadership", "rule 7: elections and leadership are told only")]}}),
    119: ({"caregiver": G}, "A child from a rival community needs temporary shelter.",
          {"eff": {1: [c.parenting("caregiver")]}}),
    120: ({"historian": SCHOLAR, "elder": EL}, "A historian compares contradictory accounts of the tribe's arrival.",
          {"eff_scene": [res("historian")]}),
}


def used_roles(nodes: dict) -> set[str]:
    out = set()
    for n in nodes.values():
        for e in n.get("effects", []):
            r = e.get("role") or (e.get("who") if e.get("who") not in (None, "all") else None)
            if r:
                out.add(r)
    return out


def finish(row, h, title, ledger, desc, roles, nodes, start, extra=None) -> dict:
    assert c.description_ok(desc), (row["id"], desc)
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in used_roles(nodes)]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
           "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": start, "nodes": nodes}
    doc.update(extra or {})
    return doc


def children(opts: dict, count: int) -> list[dict]:
    w = opts.get("w", {})
    out = []
    for k in range(1, count + 1):
        ch = {"next": f"e{k}"}
        if w:
            wt, rar = w.get(k, (20, None))
            ch["weight"] = wt
            if rar:
                ch["rarity"] = rar
        out.append(ch)
    return out


def outcome_nodes(opts: dict, lines: list[int], scene_src: str) -> dict:
    nodes = {}
    eff, tonly = opts.get("eff", {}), opts.get("to", {})
    for k, n in enumerate(lines, 1):
        node = c.page(f"Outcome {k}", c.shown(n), c.L(n), eff.get(k, []), tonly.get(k, ()))
        # the scene's own effect (061's care, 097's device): made on whichever outcome is shown, src the scene line
        scene_eff = [dict(e, src=scene_src) for e in opts.get("eff_scene", [])]
        if scene_eff:
            node["effects"] = node.get("effects", []) + scene_eff
            # the scene line's keyword reasons travel with its effects
            if tonly.get(0):
                node["text_only"] = node.get("text_only", []) + c.with_src(tonly[0], scene_src)
        nodes[f"e{k}"] = node
    return nodes


HEAD_L = r"^EVENT \d{3}\s+-\s+"


def build_l(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, opts = L_[num]
    h = c.heading_line(row, HEAD_L)
    title = re.split(HEAD_L, c.line(h), maxsplit=1)[1].strip()
    trig, scene, resp, outs, pers, effs = h + 1, h + 2, (h + 3, h + 4, h + 5), [h + 6, h + 7, h + 8], h + 9, h + 10
    assert c.line(trig).startswith("TRIGGER:") and c.line(scene).startswith("SCENE:"), row["id"]
    assert all(c.line(n).startswith("PLAYER RESPONSE ") for n in resp), row["id"]
    assert all(c.line(n).startswith(f"WEIGHTED OUTCOME {k}:") for k, n in enumerate(outs, 1)), row["id"]
    assert c.line(pers).startswith("PERSISTENCE:") and c.line(effs).startswith("EFFECTS:"), row["id"]
    assert effs == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger += [{"src": c.L(trig), "kind": "note", "why": "TRIGGER: a designer note on casting (the roles)"},
               {"src": c.L(pers), "kind": "note", "why": "PERSISTENCE: memories and callbacks, never shown (rule 9)"},
               {"src": c.L(effs), "kind": "note",
                "why": "EFFECTS: the designer's effect rule, carried out as the outcomes' effects (V28 rules)"}]
    nodes = {"scene": {"type": "question", "name": "The scene", "text": c.shown(scene), "src": c.L(scene),
                       "choices": [{"label": c.shown(n), "next": "outcome", "src": c.L(n)} for n in resp]},
             "outcome": {"type": "branch", "children": children(opts, 3)}}
    if opts.get("to", {}).get(0):
        nodes["scene"]["text_only"] = c.with_src(opts["to"][0], c.L(scene))
    nodes.update(outcome_nodes(opts, outs, c.L(scene)))
    extra = {"title_variants": opts["title_variants"]} if opts.get("title_variants") else None
    return finish(row, h, title, ledger, desc, roles, nodes, "scene", extra)


def main() -> int:
    rows_l = [r for r in c.rows("lbl") if c.num_of(r) in L_]
    assert len(rows_l) == len(L_) == 60, len(rows_l)
    docs = [(r["section"], r["id"], build_l(r)) for r in rows_l]
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
