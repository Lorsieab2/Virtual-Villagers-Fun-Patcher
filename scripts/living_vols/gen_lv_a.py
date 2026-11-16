"""Chunk LV-A: write the Living Event Engine's first three fixed event volumes as collection events, then format and
check them:
  MED-01..31     Experimental Medicine, Last Resorts & Comfort Care          living L20219-20620 (lv_med)
  LIFE-01..45    The Healer's Hands, the Farmer's Fields, and the Weaver's Dreams  L20642-21225 (lv_life)
  CIRCLE-01..31  The Circle of Life, Rights, and Remembrance                  L21244-21645 (lv_circle)
The shape, the weights and the helpers are scripts/living_vols/living_common.py's.

THE TABLE BELOW IS THE AUTHORING RECORD (the owner's rules, the lead's briefs of 2026-11-14/15):
- Text verbatim.  No sensitivity edits: nothing in these volumes names a word the owner listed for change (no
  legendary beings, afterlife names, angels or demons, complicated instruments by their modern names); the owner's
  scholarly and medical words stay; nothing is softened.
- The text names nobody and uses "their": roles carry no token.  A role casts the person an effect lands on, or the
  person the scene needs (collection.cast_only).  A healer, a scientist or botanist, a farmer, a carpenter or
  inventor the text names is skilled in the game's matching skill (Healing, Research, Farming, Building).
- Consent (MED's own rule): every outcome the source gives keeps the patient's choice as written; no effect is put
  on a path the patient refused.
- Effects only where an outcome's own words support one: a death is kill (cause "unknown": "Unknown causes"); a life
  threatened, a patient "too weak", "very weak", "critical", "dangerously" affected is serious harm (health
  -60..-40); a worsening, a reaction, swelling, nausea or pain is a minor setback (health -30..-10); "becomes ill" is
  sick; "recovers", "improves", "improved health" is a small health gain (+10..+30); an amputation (MED-05 A1, C2) is
  the owner's lasting-injury toolkit (serious health loss and a dislike of running), very rare; a healer, scientist
  or apprentice who learns, discovers or records a result gains a small skill; spoiled, ruined or lost food is a
  small food loss, food the outcome says the village gains a small food gain; buying the stranger's remedy (MED-24
  A) costs a large food loss.  Weights follow (living_common).
- Animals' deaths and disappearances, feelings, councils, customs, relationships, lasting states and later
  callbacks are text only (rules 7-9); the effects table's words that change nothing get text_only with a reason.
- Games: every game, except MED-19 (a Magic practitioner acts: VV3-VV5, as magic is VV3-VV5 lore).
- Protection: every harm-capable role keeps protected "auto" (no nursing parent, Golden Child or VV3 Chief is ever
  harmed); children may be harmed where the story makes sense (MED-14, LIFE-04).  The harm list is in
  docs/event-collection/retrofit-harm-review.md.

    python scripts/living_vols/gen_lv_a.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import living_common as c  # noqa: E402

V, G, CH, EL = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")
FARMER = c.skilled(V, "Farming")
BUILDER = c.skilled(V, "Building")
sk, minor, serious, better, ill, die, amp, food, T = (c.sk, c.minor, c.serious, c.better, c.ill, c.die,
                                                      c.amputation, c.food, c.T)
LOSS = c.food("small", loss=True)
GAIN = c.food("small")
PREMISE = "the premise: it happened before the event; nobody is harmed now"

# MED-NN: ({role: spec}, description or None (the setup), opts)
MED = {
    1: ({"healer": HEALER, "patient": G},
        "A healer wonders whether a failing organ could be replaced in a gravely ill adult.",
        {"fx": {"a1": [serious("patient")], "a2": [die("patient")], "c1": [sk("healer", "Research")],
                "c2": [sk("healer", "Healing")]}}),
    2: ({"healer": HEALER, "relative": V}, None,
        {"fx": {"a2": [sk("healer", "Research")]},
         "to": {0: [T("death", "the villager has already died: the premise; nobody dies now")]}}),
    3: ({"apprentice": HEALER, "patient": V, "volunteer": V},
        "A wounded patient is losing strength, and an apprentice proposes transferring blood from a healthy volunteer.",
        {"fx": {"a1": [minor("patient")], "b1": [better("patient")], "b2": [die("patient")],
                "c1": [sk("apprentice", "Research")]}}),
    4: ({"healer": HEALER, "patient": V}, None,
        {"fx": {"a1": [minor("patient")], "a2": [serious("patient")], "c1": [sk("healer", "Research")],
                "c2": [sk("healer", "Healing")]}}),
    5: ({"healer": HEALER, "patient": G}, None,
        {"fx": {"a1": amp("patient"), "a2": [die("patient")], "b1": [minor("patient")], "b2": [die("patient")],
                "c2": amp("patient")},
         "to": {0: [T("the injured limb", PREMISE)]}}),
    6: ({"healer": HEALER, "patient": V}, None,
        {"fx": {"a1": [better("patient")], "a2": [die("patient")], "b1": [better("patient")],
                "b2": [serious("patient")]}}),
    7: ({"patient": V, "inventor": BUILDER},
        "A patient's breathing grows shallow, and an inventor proposes a hand-operated device to move air into the lungs.",
        {"fx": {"a2": [die("patient")], "b1": [better("patient")], "b2": [serious("patient")],
                "c1": [sk("inventor", "Research")]}}),
    8: ({"healer": HEALER, "patient": V}, None,
        {"fx": {"a2": [serious("patient")], "b1": [better("patient")], "b2": [die("patient")],
                "c1": [sk("healer", "Research")], "c2": [sk("healer", "Healing")]}}),
    9: ({"elder": EL, "inventor": BUILDER}, None,
        {"fx": {"a1": [serious("elder")], "a2": [die("elder")], "b2": [die("elder")],
                "c1": [sk("inventor", "Research")]},
         "to": {0: [T("collapses", "the elder collapses, not a structure")]}}),
    10: ({"healer": HEALER, "patient": V}, None, {"fx": {"a2": [serious("patient")]}}),
    11: ({"apprentice": HEALER, "patient": V}, None,
         {"fx": {"b2": [ill("patient")], "c1": [sk("apprentice", "Research")]}}),
    12: ({"craftsperson": V, "healer": HEALER, "patient": V}, None,
         {"fx": {"a1": [minor("patient")], "a2": [sk("healer", "Healing")], "b2": [minor("patient")],
                 "c2": [sk("healer", "Healing")]}}),
    13: ({"patient": G}, None, {"fx": {"a1": [better("patient")], "b2": [minor("patient")]}}),
    14: ({"child": CH, "guardian": G, "healer": HEALER, "healer2": HEALER}, None,
         {"fx": {"a1": [better("child")], "a2": [minor("child")], "b1": [better("child")], "b2": [serious("child")],
                 "c1": [sk("healer2", "Research")]},
          "label": {"a": ("Explain the uncertain treatment to the child's guardians", True)}}),
    15: ({"patient": G}, None, {"fx": {"a2": [die("patient")]}}),
    16: ({"healer": HEALER, "friend": G}, None, {"fx": {"a2": [die("friend")]}}),
    17: ({"patient": V, "apprentice": HEALER}, None, {"fx": {"b1": [better("patient")]}}),
    18: ({"patient": V, "researcher": SCHOLAR}, None,
         {"fx": {"a2": [minor("patient")], "b1": [better("patient")], "b2": [ill("patient")],
                 "c1": [sk("researcher", "Research")]}}),
    19: ({"practitioner": V, "patient": V}, None,
         {"fx": {"a2": [die("patient")], "b1": [better("patient")]}}),
    20: ({"healer": HEALER, "patient": V, "botanist": SCHOLAR}, None,
         {"fx": {"a2": [minor("patient")], "c1": [sk("botanist", "Farming")]},
          "to": {"b1": [T("the current injury", "the patient's wound is the premise; nobody is hurt now")]}}),
    21: ({"healer": HEALER, "patient": V}, None,
         {"fx": {"b1": [sk("healer", "Research")]},
          "to": {"a2": [T("the fish dies", "an animal, not a villager")]}}),
    22: ({"apprentice": HEALER, "patient": V}, None, {"fx": {"b1": [sk("apprentice", "Research")]}}),
    23: ({"patient": V, "healer": HEALER}, None, {}),
    24: ({"patient": V}, None,
         {"fx": {"a1": [food("large", loss=True), better("patient")], "a2": [food("large", loss=True)],
                 "b1": [better("patient")], "b2": [die("patient")]},
          "label": {"c": ("Ask the stranger to demonstrate the remedy", True)}}),
    25: ({"patient": G}, None, {"fx": {"a1": [die("patient")]}}),
    26: ({"patient": V}, None,
         {"fx": {"a1": [better("patient")], "a2": [serious("patient")], "b2": [die("patient")]}}),
    27: ({"patient1": V, "patient2": V, "healer": HEALER}, None,
         {"fx": {"a1": [minor("patient2")], "a2": [better("patient1"), better("patient2")],
                 "b1": [sk("healer", "Research")], "b2": [minor("patient1")], "c1": [sk("healer", "Research")]}}),
    28: ({"patient": V, "healer": HEALER}, None,
         {"fx": {"a1": [die("patient")], "a2": [serious("patient")], "b2": [die("patient")]}}),
    29: ({"patient": G, "healer": HEALER}, None,
         {"fx": {"c2": [minor("patient")]},
          "to": {"b1": [T("experience modest relief", "the patients feel relief: no skill is meant")]}}),
    30: ({"scientist": SCHOLAR, "patient": V}, None,
         {"fx": {"a1": [better("patient")], "a2": [minor("patient")], "b1": [sk("scientist", "Research")]}}),
    31: ({"healer": HEALER, "elder": EL}, None, {"fx": {"b2": [sk("healer", "Research")]}}),
}

LIFE = {
    1: ({"healer": HEALER, "patient": V}, None,
        {"fx": {"a1": [minor("patient")]}, "to": {"b1": [T("the injury still hurts", PREMISE)]}}),
    2: ({"healer": HEALER, "patient": V},
        "A healer's strong plant draught may dull pain during a difficult procedure, but may also slow breathing.",
        {"fx": {"a1": [minor("patient")], "a2": [serious("patient")], "c2": [minor("patient")]}}),
    3: ({"apprentice": HEALER, "patient": V}, None, {"fx": {"a1": [sk("apprentice", "Healing")]}}),
    4: ({"child": CH, "healer": HEALER}, None, {"fx": {"a2": [minor("child")]}}),
    5: ({"carpenter": BUILDER, "healer": HEALER, "patient": V}, None,
        {"fx": {"c1": [sk("carpenter", "Building")]},
         "to": {"c2": [T("the injured villager", "the broken leg is the premise; nobody is hurt now")]}}),
    6: ({"elder": EL}, None, {"fx": {"a2": [serious("elder")]}}),
    7: ({"patient": V}, None, {"fx": {"b2": [minor("patient")]}}),
    8: ({"patient": V, "healer": HEALER}, None, {}),
    9: ({"patient": V, "healer": HEALER}, None, {"fx": {"a2": [minor("patient")], "b2": [minor("patient")]}}),
    10: ({"fisherman": c.sexed(V, "male"), "healer": HEALER}, None,
         {"fx": {"a1": [better("fisherman")], "a2": [minor("fisherman")], "b1": [better("fisherman")],
                 "b2": [minor("fisherman")], "c1": [sk("healer", "Healing")]}}),
    11: ({"farmer": FARMER, "cook": V}, None,
         {"fx": {"a1": [LOSS], "a2": [sk("farmer", "Farming")], "b1": [GAIN], "b2": [LOSS],
                 "c1": [sk("farmer", "Farming")]},
          "to": {"a2": [T("food", "the lesson is how to protect drying food; nothing is gained or lost")],
                 "b1": [T("dislike the taste", "some villagers, not a cast one: no preference changes")],
                 "c1": [T("food", "the village learns which method suits each food; nothing is gained or lost")]}}),
    12: ({"potter": V, "healer": HEALER}, None,
         {"fx": {"a1": [LOSS], "b2": [LOSS], "c2": [LOSS]},
          "to": {0: [T("preserve food", "the question of the event; nothing is gained or lost on this page")]}}),
    13: ({"fisher": V}, None,
         {"fx": {"b2": [LOSS]},
          "to": {"c2": [T("food stores", "the smaller stores of this choice; nothing more is lost")]}}),
    14: ({"farmer": FARMER}, None, {"fx": {"a1": [LOSS], "b2": [LOSS]}}),
    15: ({"child": CH, "elder": EL}, None, {}),
    16: ({"farmer": FARMER}, None, {}),
    17: ({"boatbuilder": BUILDER, "fisher": V}, None,
         {"to": {"c1": [T("celebrate", "rule 7: the fishers' own gladness, not a village celebration")]}}),
    18: ({"gardener": FARMER, "scientist": SCHOLAR}, None,
         {"fx": {"a1": [GAIN], "c1": [sk("scientist", "Research")]}}),
    19: ({"novice": V}, None, {"fx": {"a2": [LOSS]}}),
    20: ({"weaver": V}, None, {"to": {0: [T("vanished", "a plant nearly vanished; no villager vanishes")]}}),
    21: ({"elder": EL, "scribe": V, "apprentice": V}, None,
         {"fx": {"b2": [LOSS]},
          "to": {0: [T("dislikes written records", "the elder's view of records, not a game preference")]}}),
    22: ({"explorer": c.YOUNG, "elder": EL}, None, {}),
    23: ({"musician": V, "child": CH}, None, {}),
    24: ({"drummer": c.YOUNG, "elder": EL}, None, {}),
    25: ({"inventor": V}, None, {}),
    26: ({"weaver": V, "elder": EL}, None, {}),
    27: ({"elder": EL, "child": CH}, None, {}),
    28: ({"historian": SCHOLAR}, None, {}),
    29: ({"tailor": V}, None, {}),
    30: ({"craftsperson": V}, None, {}),
    31: ({"dyer": V, "child": CH, "scientist": SCHOLAR}, None, {}),
    32: ({"apprentice": V}, None, {}),
    33: ({"sailor": V}, None, {}),
    34: ({"gatherer": V}, None,
         {"fx": {"b2": [LOSS]}, "to": {0: [T("food gatherers", "who the gatherers are; nothing is gained or lost")]}}),
    35: ({"partner1": G, "partner2": G}, None, {}),
    36: ({"tailor": V, "botanist": SCHOLAR}, None, {}),
    37: ({"weaver": V}, None, {}),
    38: ({"fisher": V}, None, {"fx": {"a1": [GAIN]}}),
    39: ({"grower": FARMER, "child": CH}, None, {"fx": {"b1": [LOSS]}}),
    40: ({"farmer": FARMER, "naturalist": SCHOLAR, "child": CH}, None, {"fx": {"b1": [GAIN]}}),
    41: ({"miner": V}, None, {"fx": {"a1": [LOSS]}}),
    42: ({"dyer": V}, None, {}),
    43: ({"weaver": V, "scribe": V}, None, {}),
    44: ({"healer": HEALER, "patient": V}, None, {}),
    45: ({"weaver": c.YOUNG, "elder": EL}, None, {}),
}

CIRCLE = {
    1: ({"child": CH, "relative": G}, None,
        {"to": {0: [T("death", "the father's death is the premise; nobody dies now")]}}),
    2: ({"fisher": V, "child": CH}, None,
        {"to": {0: [T("food stores run low", "the premise: the stores are already low; nothing is lost now")]}}),
    3: ({"scientist": SCHOLAR, "child": CH}, None, {"fx": {"a1": [sk("scientist", "Research")]}}),
    4: ({"carpenter": BUILDER, "youngster": c.YOUNGSTER}, None, {}),
    5: ({"parent": G, "child": CH}, None,
        {"fx": {"b2": [GAIN]},
         "to": {0: [T("a shortage of food", "the premise: the shortage already exists; nothing is lost now")]}}),
    6: ({"keeper": V}, None, {"to": {"c1": [T("food", "the parrot learns to find its own food")]}}),
    7: ({"scientist": SCHOLAR, "fisher": V}, None,
        {"fx": {"a1": [sk("scientist", "Research")], "c2": [LOSS]}}),
    8: ({"scientist": SCHOLAR, "apprentice": V}, None, {}),
    9: ({"fisher": EL, "apprentice": V}, None,
        {"to": {0: [T("taken for food", "the custom's subject; nothing is gained or lost")]}}),
    10: ({"keeper": V}, None, {"fx": {"b1": [LOSS], "b2": [LOSS]}}),
    11: ({"child": CH, "parent": G}, None, {"fx": {"c2": [sk("parent", "Parenting")]}}),
    12: ({"villager": V}, None, {}),
    13: ({"elder": c.sexed(EL, "female"), "relative": V}, None,
         {"to": {0: [T("death approaching", "the elder senses it; no outcome says she dies")]}}),
    14: ({"child": CH, "adult": G}, None,
         {"to": {0: [T("a sibling dies", "the sibling's death is the premise; nobody dies now")]}}),
    15: ({"parent": G}, None,
         {"to": {"a1": [T("the letters vanish", "the writing in the sand, not a villager")]}}),
    16: ({"child": CH, "elder": EL}, None,
         {"to": {0: [T("death", "the mother's death is the premise; nobody dies now")]}}),
    17: ({"healer": HEALER, "apprentice": V}, None, {"fx": {"c1": [sk("healer", "Research")]}}),
    18: ({"hunter": V}, None, {}),
    19: ({"villager": V}, None,
         {"to": {"a1": [T("dislike harvesting there", "some families, not a cast one: no preference changes")]}}),
    20: ({"cook": V, "scientist": SCHOLAR}, None,
         {"fx": {"a1": [LOSS], "a2": [ill("cook")], "b1": [sk("scientist", "Research")], "c1": [GAIN]}}),
    21: ({"villager": V}, None, {"fx": {"a1": [GAIN], "a2": [LOSS]}}),
    22: ({"villager": V}, None, {}),
    23: ({"child": CH, "jeweler": V}, None, {}),
    24: ({"child": CH}, None, {"to": {"b2": [T("disappears", "the otter, not a villager")]}}),
    25: ({"councilor": G}, None, {}),
    26: ({"villager": V, "healer": HEALER}, None, {"to": {0: [T("refuses food", "the dog, not the village's food")],
                                                                  "a1": [T("dies", "the dog, not a villager")]}}),
    27: ({"elder": EL, "scientist": SCHOLAR}, None, {}),
    28: ({"botanist": SCHOLAR}, None,
         {"to": {"a1": [T("vanish", "the tree may vanish from Isola, not a villager")]}}),
    29: ({"weaver": V}, None, {}),
    30: ({"child": CH, "parent": G}, None, {"fx": {"a2": [sk("parent", "Parenting")]}}),
    31: ({"villager": V, "child": CH}, None, {}),
}

VOLUMES = (("lv_med", MED, 31), ("lv_life", LIFE, 45), ("lv_circle", CIRCLE, 31))


def main() -> int:
    docs = []
    for section, table, count in VOLUMES:
        rows = c.rows(section)
        assert len(rows) == len(table) == count, (section, len(rows), len(table))
        for r in rows:
            roles, desc, opts = table[c.num_of(r)]
            docs.append((section, r["id"], c.build(r, roles, desc, opts)))
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
