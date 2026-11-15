"""Chunk K5: write the Companion Anthology's Volume 1 Part 4 events N051-N069 (companion L3135-3307) as
data/event_collection/companion/c5/c5dn<NNN>_<slug>.json, and The Lives Between Legends events 001-060 (companion
L3793-4590) as data/event_collection/companion/lbl/lbl<NNN>_<slug>.json, then format and check them.

PART 4 N051-N069 (chunk K4's gen_k4.py builds N001-N050 the same way; this file copies its approach):
  group heading (above N060: UNEXPECTED SOCIAL LIFE AND SMALL CONSEQUENCES) / EVENT Nnnn - Title / SETUP: /
  ALTERNATIVE OUTCOMES: / 1. 2. 3. / CHOICES: No choice by default; ... (the same in all 69).
- One popup: the setup, then one of the three outcomes appended, equally likely (no odds given).  "ALTERNATIVE
  OUTCOMES:" is structural; "CHOICES: No choice by default; ..." is a designer note.  The outcomes written as actions
  ("Apologize sincerely without demanding forgiveness.") ship as written (inventory Q2 / Q-imperatives).
- The volume's L37-48 rule: "Childcare scenes give the caregiver Parenting": the caregiver(s) of N056 and N057 gain a
  small Parenting on every outcome.  N069's researcher who records the observation gains a small Research.
- N067 "Someone makes a joke and diffuses it." -> "defuses it" (grammar-fixes.md, companion L3286).

THE LIVES BETWEEN LEGENDS 001-060 (engine rules L3779-3787):
  group heading between separator lines / EVENT NNN - Title / TRIGGER: (the same in all 120) / SCENE: /
  PLAYER RESPONSE A-C (the same three in all 120) / WEIGHTED OUTCOME 1-3: / PERSISTENCE: / EFFECTS: (the same in all).
- The scene is the question page; the three responses are the source's own labels, each with its own src, and all
  lead to the SAME outcome branch (L3782: "The branches are not necessarily tied one-to-one to choices").  No odds are
  given: the outcomes are equal, except a harm the V28 rules call rare (an illness, a disappearance, 044's "rare fatal
  outcome": 5 against 20) and a minor setback the V27 global rule calls occasional (026's, 027's and 059's minor
  injuries: 10 against 20).  TRIGGER, PERSISTENCE and EFFECTS are designer notes (rule 9: memories and callbacks).
- Casting (the lead's decisions): elders 55+; "a toddler" 3-7; "a young villager" 3-17; a child who looks after a
  YOUNGER sibling is 8-13 and the sibling 3-7.  Kinship the text states is a relation (cie-v6-binary.md 21): parents,
  children and siblings.  Grandchildren, cousins, "relatives", descendants: no relation kind (gap C2): cast by age,
  text only.  Romance pairs (013, 014, 019, 020, 022, 024) are adults at most 10 years apart (L3781 "age-appropriate
  participants"); 030's are both teens.  Genders are random (L3780) except a "father" (male) and a mother (female).
- Babies are not villagers: a baby is its nursing parent's state.  A baby scene casts the nursing parent (special
  nursing_parent, female: L3780 "Nursing/breastfeeding is reserved for female characters"), harmless, except 044,
  whose "rare fatal outcome" is baby_lost on that parent with protected "allow" (retrofit-harm-review.md, "Companion
  K5").  043's mother whose baby already died is an adult woman; the baby is text (the lead's decision, Q10).
- Effects (the V28 consequence rules, only on an outcome whose text supports it):
  caregiving earns a small Parenting: the caregiver the scene shows caring gains it on every outcome (003, 008, 038,
  041, 042, 044 outcomes 1-2, 045, 046), and a parent or adult who steps in on one outcome gains it there (004, 012,
  046's father, 048);  hands-on work earns a small skill in the game skill it is: 006 "discovers a skill" (one of the
  four), 038's healer checks for illness (Healing), 057's historian identifies the owner (Research);  harm:
  016 the hurt apprentice (a minor injury on every outcome: the scene says one is hurt), 025 the child who falls ill
  (sick, rare), 026 one injured in the rescue (minor) and the participant who disappears (vanish, rare: missing is
  not dead), 027 the fall's treatable injury (minor), 059 the elder's strain (minor), 044 the baby (baby_lost, rare).
  Everything else is text: courtship, trust, councils, traditions, archives and memories (rules 7 and 9), crafts and
  navigation no game has as a skill (rule 8).

    python scripts/companion/gen_k5.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

V, G, CH, EL, TEEN, ANY = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN, c.ANY_AGE
LITTLE = {"kind": "villager", "min_age": 3, "max_age": 7}           # "a toddler", a younger sibling
OLDER_CHILD = {"kind": "villager", "min_age": 8, "max_age": 13}     # a child minding a younger sibling
YOUNG = {"kind": "villager", "min_age": 3, "max_age": 17}           # "a young villager", a pupil, a grandchild
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")                                  # a researcher, a historian
MALE, FEMALE = c.sexed(G, "male"), c.sexed(G, "female")
NURSING = {"kind": "villager", "min_age": 18, "sex": "female", "special": "nursing_parent"}
NURSING_HARMED = dict(NURSING, protected="allow")                  # 044 only: retrofit-harm-review.md
FOUR = ["Building", "Farming", "Healing", "Research"]
T = c.text_only
MINOR = (-30, -10)                                                  # a minor injury (companion-authoring.md 6)


def couple(base: dict, other: str) -> dict:
    """A romance partner: age-appropriate, at most 10 years from `other` (L3781)."""
    return dict(base, max_age_gap={"role": other, "years": 10})


def hurt(role: str, src: str | None = None) -> dict:
    e = {"do": "health_change", "role": role, "min": MINOR[0], "max": MINOR[1]}
    if src:
        e["src"] = src
    return e


def res(role: str) -> dict:
    return c.skill(role, "Research")


RARE = (5, "rare")
OCCASIONAL = (10, "occasional")   # a minor setback (the V27 global rule; collection_check weight 10)

# ---- Part 4, N051-N069 ------------------------------------------------------------------------------------------------
HEAD_D = r"^EVENT N\d{3}\s+-\s+"

# num: ({role: spec}, description, opts)
# opts: eff {k: [effects]}, to {k or 0: [text_only]}, w {k: (weight, rarity)}, fix {k: (before, after)},
#       carers [roles: Parenting on every outcome]
D = {
    51: ({"child": CH, "friend": CH}, "A child realizes their friend heard a hurtful comment.", {}),
    52: ({"friend1": CH, "friend2": CH, "newcomer": CH},
         "Two close friends struggle when a third child wants to join their games.", {}),
    53: ({"child": CH}, "A child becomes separated from their group near unfamiliar trees.", {}),
    54: ({"child": OLDER_CHILD, "sibling": c.related(LITTLE, "sibling_of", "child")},
         "A child thinks a younger sibling has gone missing.", {}),
    55: ({"child1": CH, "child2": CH, "child3": CH}, "Several children form a club with elaborate membership rules.", {}),
    56: ({"child": CH, "caregiver": c.related(G, "parent_of", "child")},
         "A caregiver worries that a child never shows sadness.", {"carers": ["caregiver"]}),
    57: ({"caregiver1": NURSING, "caregiver2": G}, "A baby seems to prefer one caregiver, upsetting another.",
         {"carers": ["caregiver1", "caregiver2"]}),
    58: ({"elder": EL, "child1": CH, "child2": CH}, "An elder invites children to learn an old craft.", {}),
    59: ({"child": CH, "friend": CH}, "A child spends a night in a friend's household.", {}),
    60: ({"villager1": V, "villager2": V, "villager3": V},
         "A scheduling mistake leaves several villagers with a free afternoon.", {}),
    61: ({"rival1": V, "rival2": V}, "Two rivals take shelter beneath the same giant leaf.", {}),
    62: ({"villager": V, "elder": EL, "child": CH}, "A villager admits they dislike their childhood nickname.",
         {"to": {0: [T("dislike", "a dislike of a nickname; a nickname is no game preference (rule 8)")]}}),
    63: ({"villager": V}, "Someone receives a beautifully wrapped package containing a single smooth stone.", {}),
    64: ({"villager": V, "friend": V}, "At a gathering, a shy villager finds every seat taken.", {}),
    65: ({"villager": V}, "A family invents a tiny ritual for ordinary Tuesdays.", {}),
    66: ({"friend1": V, "friend2": V}, "Two former childhood friends meet after years apart.", {}),
    67: ({"relative1": V, "relative2": V}, "A disagreement about a trivial chore nearly becomes a family feud.",
         {"fix": {1: ("diffuses it", "defuses it")}}),
    68: ({"villager": V, "owner": V}, "A villager accidentally damages an object with deep sentimental value.", {}),
    69: ({"researcher": SCHOLAR, "child": CH},
         "A researcher finds that a particular pebble makes a satisfying clicking sound.", {"eff": {1: [res("researcher")]}}),
}

# ---- The Lives Between Legends, 001-060 ---------------------------------------------------------------------------------
HEAD_L = r"^EVENT \d{3}\s+-\s+"
SCENE = "scene"            # opts["eff_scene"]: effects made on every outcome, src the scene line

L_ = {
    1: ({"elder": EL}, "An elder finds a sealed letter written by a deceased partner.", {}),
    2: ({"child": CH, "parent": c.related(G, "parent_of", "child")},
        "A family notices a child resembles a distant relative.", {}),
    3: ({"parent": G, "child": c.related(CH, "child_of", "parent")},
        "A parent is exhausted by caring for several children.", {"carers": ["parent"]}),
    4: ({"sibling1": YOUNG, "sibling2": c.related(YOUNG, "sibling_of", "sibling1"),
         "parent": c.related(G, "parent_of", "sibling1")},
        "Two siblings disagree about which one receives more attention.", {"eff": {1: [c.parenting("parent")]}}),
    5: ({"villager": G, "adult_child": c.related(G, "child_of", "villager")},
        "A widowed villager considers a new relationship.", {}),
    6: ({"teen": TEEN, "sibling": c.related(V, "sibling_of", "teen"), "guardian": c.related(G, "parent_of", "teen")},
        "A guardian compares a teen to their accomplished sibling.", {"eff": {1: [c.skill("teen", FOUR)]}}),
    7: ({"relative1": V, "relative2": V, "child": CH}, "Two relatives have not spoken since a bitter argument.", {}),
    8: ({"guardian": G, "child": CH}, "A villager promised to raise a friend's child if needed.",
        {"carers": ["guardian"]}),
    9: ({"cook": V, "cousin": V}, "A cook inherits a recipe with one ingredient missing.", {}),
    10: ({"relative1": V, "relative2": V}, "Two relatives celebrate birthdays on the same day.",
         {"to": {0: [T("celebrate", "a family's birthdays, not the village's celebration (rule 7)")],
                 2: [T("celebration", "one relative's wish for a birthday of their own (rule 7)")]}}),
    11: ({"elder": EL, "grandchild": YOUNG}, "An elder studies a carving depicting relatives now gone.", {}),
    12: ({"child": CH, "adult": G}, "A child without available caregivers bonds with a reserved adult.",
         {"eff": {1: [c.parenting("adult")]}}),
    13: ({"villager": G, "friend": couple(G, "villager")}, "A villager plans to confess affection to a close friend.", {}),
    14: ({"friend1": G, "friend2": couple(G, "friend1")},
         "Two villagers are inseparable but refuse to explain their bond.", {}),
    15: ({"villager": V, "friend": V}, "A villager learns everyone else attended a gathering.", {}),
    16: ({"injured": V, "rival": V}, "Two competing apprentices face a difficult day when one is hurt.",
         {"eff_scene": [hurt("injured")]}),
    17: ({"dancer": V, "friend": V}, "A villager's awkward dance becomes a village joke.", {}),
    18: ({"roommate1": V, "roommate2": V}, "Two villagers with opposite habits share a hut.", {}),
    19: ({"friend": V, "partner1": G, "partner2": couple(G, "partner1")},
         "A friend feels forgotten after two companions begin dating.", {}),
    20: ({"villager": G, "beloved": couple(G, "villager")},
         "A romantic confession is disrupted by a wandering pig.", {}),
    21: ({"friend1": V, "friend2": V}, "Two childhood friends meet after years of distance.", {}),
    22: ({"villager": G, "giver": couple(G, "villager")}, "A villager receives small anonymous gifts.", {}),
    23: ({"critic": V, "friend": V}, "A blunt villager critiques a friend's new creation.", {}),
    24: ({"partner1": G, "partner2": couple(G, "partner1")},
         "A couple's planned celebration loses its musicians to bad weather.",
         {"to": {0: [T("celebration", "a couple's wedding, not the village's celebration (rule 7)")]}}),
    25: ({"child1": CH, "child2": CH, "child3": CH},
         "Several children slip away to explore without telling their guardians.",
         {"eff": {3: [{"do": "sick", "role": "child1"}]}, "w": {3: RARE}}),
    26: ({"teen1": TEEN, "teen2": TEEN, "teen3": TEEN}, "Teenagers launch a homemade raft after dark.",
         {"eff": {2: [hurt("teen1")], 3: [{"do": "vanish", "role": "teen2"}]}, "w": {2: OCCASIONAL, 3: RARE},
          "to": {3: [T("death", "missing is not dead (L3784): the teen vanishes, no death and no grave")]}}),
    27: ({"child": CH, "friend": CH}, "A child accepts a challenge to climb an unstable tree.",
         {"eff": {3: [hurt("child")]}, "w": {3: OCCASIONAL}}),
    28: ({"child": CH, "friend": CH}, "A child takes a friend's favorite shell pendant.", {}),
    29: ({"teen1": TEEN, "teen2": TEEN, "friend": TEEN}, "A teen imitates another teen's voice for laughs.", {}),
    30: ({"teen": TEEN, "peer": TEEN}, "A teenager realizes they enjoy spending time with a peer.", {}),
    31: ({"pupil": YOUNG, "teacher": G, "classmate": YOUNG}, "A confident pupil interrupts a lesson with a bold claim.", {}),
    32: ({"child1": CH, "child2": CH, "elder": EL}, "Children protest a rule they believe favors older villagers.", {}),
    33: ({"child": OLDER_CHILD, "sibling": c.related(LITTLE, "sibling_of", "child")},
         "A child realizes their younger sibling has wandered away.", {}),
    34: ({"maker": YOUNG, "friend": YOUNG}, "A young craftsperson promises a friend a carved toy.", {}),
    35: ({"teen": TEEN, "friend": TEEN}, "A teen witnesses a friend's dangerous mistake.", {}),
    36: ({"teen": TEEN}, "A teen is asked to supervise a small task independently.", {}),
    37: ({"parent": NURSING, "villager": V}, "A baby bursts into laughter whenever a certain villager approaches.", {}),
    38: ({"parent": NURSING, "healer": HEALER}, "A baby cries through several nights.",
         {"carers": ["parent"], "eff": {2: [c.skill("healer", "Healing")]}}),
    39: ({"elder": EL, "parent": NURSING}, "A baby refuses to release an elder's finger.", {}),
    40: ({"caregiver1": NURSING, "caregiver2": G},
         "Two caregivers accidentally exchange similar blankets at a gathering.", {}),
    41: ({"toddler": LITTLE, "caregiver": c.related(G, "parent_of", "toddler")},
         "A toddler attempts to walk toward a familiar face.",
         {"carers": ["caregiver"],
          "to": {1: [T("celebrate", "a toddler and caregiver celebrate, not the village (rule 7)")]}}),
    42: ({"father": MALE}, "A father invents a soothing song while holding his baby.", {"carers": ["father"]}),
    43: ({"mother": FEMALE, "relative": V}, "A nursing mother is devastated after the death of her baby.",
         {"to": {0: [T("death", "the baby's death is the premise, already past; a baby is no villager (Q10: the "
                                "mother is cast, the baby is text)")]}}),
    44: ({"mother": NURSING_HARMED}, "A baby becomes ill during a difficult season.",
         {"eff": {1: [c.parenting("mother")], 2: [c.parenting("mother")],
                  3: [{"do": "baby_lost", "role": "mother"}]},
          "w": {3: RARE},
          "to": {2: [T("remains ill", "a nursing baby is its parent's state, not a villager: no sick effect can "
                                      "reach it")]}}),
    45: ({"caregiver": NURSING, "sibling": c.related(CH, "child_of", "caregiver")},
         "A baby repeatedly reaches for a caregiver's necklace.", {"carers": ["caregiver"]}),
    46: ({"childcarer": G, "father": MALE}, "A childcarer feels overwhelmed by several babies and toddlers.",
         {"carers": ["childcarer"], "eff": {2: [c.parenting("father")]}}),
    47: ({"relative1": G, "relative2": G, "caregiver": G}, "Relatives disagree over what a baby's first word meant.", {}),
    48: ({"sibling": CH, "parent": c.related(G, "parent_of", "sibling")},
         "A family must confront the death of an infant.",
         {"eff": {1: [c.parenting("parent")]},
          "to": {0: [T("death", "the infant's death is the premise, already past; a baby is no villager")]}}),
    49: ({"elder": EL, "relative": V}, "An elder asks to visit a childhood landmark by canoe.", {}),
    50: ({"elder1": EL, "elder2": EL}, "Two elders remember the same founding event differently.", {}),
    51: ({"master": G, "apprentice": V}, "A master artisan chooses one final student.", {}),
    52: ({"elder": EL, "child": CH}, "An elder decides to learn a completely unfamiliar craft.", {}),
    53: ({"elder": EL, "friend": V}, "An elder forgets the name of a longtime friend.",
         {"to": {3: [T("health check", "a respectful check, not a change: nobody's health moves")]}}),
    54: ({"elder": EL, "grandchild": YOUNG}, "An elder's account of a shipwreck shapes a grandchild's ambitions.", {}),
    55: ({"elder": EL, "rival": V}, "A longtime rival sends an elder a carefully made present.", {}),
    56: ({"elder": EL}, "An elder stops performing a demanding job.", {}),
    57: ({"villager": V, "historian": SCHOLAR, "artisan": V},
         "A family discovers a tool with an unfamiliar maker's mark.", {"eff": {1: [res("historian")]}}),
    58: ({"elder": EL, "child": CH, "teen": TEEN}, "An elder shares a lesson they wish they had learned earlier.", {}),
    59: ({"elder": EL, "helper": V}, "An aging villager insists on carrying heavy supplies.",
         {"eff": {3: [hurt("elder")]}, "w": {3: OCCASIONAL}}),
    60: ({"villager": V}, "The community gathers to remember villagers who have died or disappeared.",
         {"to": {0: [T("died", "the remembered dead are past; nobody dies now"),
                     T("disappeared", "the remembered missing are past; nobody vanishes now")]}}),
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


def outcome_nodes(opts: dict, lines: list[int], fixes: list, append: bool, scene_src: str) -> dict:
    nodes = {}
    eff, tonly, fix = opts.get("eff", {}), opts.get("to", {}), opts.get("fix", {})
    for k, n in enumerate(lines, 1):
        effects = [c.parenting(r) for r in opts.get("carers", [])] + eff.get(k, [])
        fx = {}
        if k in fix:
            fixes.append({"src": c.L(n), "before": fix[k][0], "after": fix[k][1]})
            fx = {n: [fix[k]]}
        with c.lib.use_source(c.lib.COMPANION_ID):
            text = c.cc.processed_line(n, {}, fx)
        text = text[:1].upper() + text[1:]
        node = c.page(f"Outcome {k}", text, c.L(n), effects, tonly.get(k, ()), append=append)
        # the scene's own harm (016 "one is hurt"): made on whichever outcome is shown, src the scene line
        scene_eff = [dict(e, src=scene_src) for e in opts.get("eff_scene", [])]
        if scene_eff:
            node["effects"] = node.get("effects", []) + scene_eff
        nodes[f"e{k}"] = node
    return nodes


def build_d(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, opts = D[num]
    h = c.heading_line(row, HEAD_D)
    title = re.split(HEAD_D, c.line(h), maxsplit=1)[1].strip()
    setup, alt, note = h + 1, h + 2, h + 6
    assert c.line(setup).startswith("SETUP:") and c.line(alt).strip() == "ALTERNATIVE OUTCOMES:", row["id"]
    assert c.line(note).startswith("CHOICES: No choice by default;") and note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger += [{"src": c.L(alt), "kind": "structural", "why": "the outcomes' heading: one is drawn"},
               {"src": c.L(note), "kind": "note",
                "why": "CHOICES: No choice by default; a designer note: the event is one popup, one outcome drawn"}]
    fixes: list = []
    nodes = {"setup": {"name": "The setup", "text": c.shown(setup), "src": c.L(setup), "children": children(opts, 3)}}
    if opts.get("to", {}).get(0):
        nodes["setup"]["text_only"] = c.with_src(opts["to"][0], c.L(setup))
    nodes.update(outcome_nodes(opts, [h + 3, h + 4, h + 5], fixes, True, c.L(setup)))
    return finish(row, h, title, ledger, desc, roles, nodes, "setup", {"grammar_fixes": fixes} if fixes else None)


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
    nodes.update(outcome_nodes(opts, outs, [], False, c.L(scene)))
    return finish(row, h, title, ledger, desc, roles, nodes, "scene")


def main() -> int:
    rows_d = [r for r in c.rows("c5dn") if c.num_of(r) in D]
    rows_l = [r for r in c.rows("lbl") if c.num_of(r) in L_]
    assert len(rows_d) == len(D) == 19 and len(rows_l) == len(L_) == 60, (len(rows_d), len(rows_l))
    docs = [(r["section"], r["id"], build_d(r)) for r in rows_d] + [(r["section"], r["id"], build_l(r)) for r in rows_l]
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
