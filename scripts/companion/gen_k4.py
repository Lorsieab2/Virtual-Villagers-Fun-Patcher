"""Chunk K4: write the Companion Anthology's Volume 1 Part 4, New Specialties & Social Life, events N001-N050
(companion L2662-3132), and Part 5, Material Culture, Foodways, Community & Belief, events V031-V050 and V060
(companion L3542-3742), as data/event_collection/companion/c5/c5dn<NNN>_<slug>.json and c5ev<NNN>_<slug>.json, then
format and check them.  Chunk K3's gen_k3.py builds Part 5 V001-V030 the same way; this file copies its approach.

PART 4 (L2657-2659; events N001-N069, N051-N069 are chunk K5's):
  group heading (COMING OF AGE - AGES 14-17 ONLY, FOOD, SWEETS..., MUSHROOMS..., MUSIC..., HEALERS..., CHILDREN...)
  / EVENT Nnnn - Title / SETUP: / ALTERNATIVE OUTCOMES: / 1. 2. 3. / CHOICES: No choice by default; ... (the same
  in all 69).
- One popup: the setup, then one of the three outcomes appended, equally likely (no odds given).  "ALTERNATIVE
  OUTCOMES:" is structural; "CHOICES: No choice by default; ..." is a designer note.
- The mushroom tags ("FLAVOR:", "TEMPORARY:", "PERSISTENT:", "MECHANICAL:", "SEVERE:", "RARE FATAL:", "SAFE:") are
  designer tags: ledger notes cut from the line.  The words after them ship as written when they are a story line
  ("the eater insists on walking backward for the afternoon.").  An outcome that is only a mechanical instruction
  ("change hair color to a valid palette option.", "modest Research skill gain.") is an `instruction` ledger entry:
  the outcome is a silent node carrying the effect (or a text_only reason), and the popup shows the setup alone.
  Instructions inside an outcome ("; gain a small skill boost", "if the fatal branch is enabled") are cut the same way.
- Ages: the coming-of-age group is "AGES 14-17 ONLY" (and the volume's L37 rule: career events are for 14-17), so its
  young villagers are TEEN; elsewhere a "young cook" is 14-25 and a child 3-13.  ELDER is 55+.
- Effects (the source's instructions; the V28 consequence rules otherwise: only where the text clearly supports one):
  N001 a small skill of the four the setup names, and a dislike of "work" ("Dislike the first job ... update a
  preference"); N004 a like of "herbs" ("a preference for medicinal botany"); N005 a small Building ("gain both
  skills"; music is no game skill); N019 a random head ("change hair color", the appearance effect); N021 a small
  Research ("modest Research skill gain"); N022 a small skill loss, one skill at random ("small random skill loss");
  N023 sick ("SEVERE: poisoning") and a death, cause unknown ("RARE FATAL: villager dies"), both rare (5 against
  20, the source's "RARE" and the V28 weight for a serious illness); N024 a small Research ("Researchers document");
  N041 the healer celebrates ("Celebrate with the care team"); N046, N047 the caregiver's small Parenting on every
  outcome (the volume's L37 rule) and N047's apprentice "learns supervised childcare"; N049 the teacher's Parenting
  on every outcome; N050 the adult who helps (outcome 3) gains Parenting.  N020's "random valid like / dislike" has
  no effect: the format has no random preference (gap C1), so it is text only.  No role uses protected "allow".

PART 5 V031-V050: as gen_k3.py (one popup, the setup and one of OUTCOME A / B appended).  V042's "where the game
supports it" is an instruction cut (the magic is text).  Nobody is harmed and no skill moves: the outcomes are
conversations, leadership and beliefs (rule 7).

V060 "How Did We Get Here?" (L3690-3742): the manifest's title (the source's "(VV1-VV5 CONDITIONAL ORIGIN STORIES)"
suffix is a designer note).  A silent branch by game opens each game's own question page: the setup and that game's
accounts only (the source: "Never display a game's other origin variants"), with the three PLAYER OPTIONS, all
leading to the five POSSIBLE OUTCOMES, equally likely.  The Tree of Life's "the Chief" is {@chief}; New Believers'
"the Heathens" has its Guardians of Isola Rewrite form "the Isolans" (guardians-wording.md).  "A researcher gains a
modest History/Research experience increment" gives the researcher a small Research.

    python scripts/companion/gen_k4.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

V, G, CH, EL, TEEN = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN
BUILDER = c.skilled(V, "Building")
FARMER = c.skilled(V, "Farming")
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")                                  # a researcher, a naturalist
YOUNG_COOK = {"kind": "villager", "min_age": 14, "max_age": 25}     # "a young cook" (N013)
RETIRED_HEALER = c.skilled(EL, "Healing")                           # "a retired healer" (N044)
FOUR = ["Farming", "Building", "Healing", "Research"]               # N001's setup: farming, building, healing, research
EVERY_SKILL = ["Parenting", "Building", "Farming", "Healing", "Research", "Devotion"]

TAG_RE = re.compile(r"^\s*\d\.\s+((?:RARE )?[A-Z]{4,}):\s")         # FLAVOR: TEMPORARY: ... RARE FATAL:


def res(role: str) -> dict:
    return c.skill(role, "Research")


def bld(role: str) -> dict:
    return c.skill(role, "Building")


def loss(role: str, skills) -> dict:
    e = c.skill(role, skills)
    e["min"], e["max"] = -e["max"], -e["min"]
    return e


def like(role: str, word: str, lst: str = "likes") -> dict:
    return {"do": "preference", "role": role, "list": lst, "preference": word}


T = c.text_only
NO_RANDOM_PREF = "gap C1: the format has no random preference, so the like / dislike is text only"

# ---- Part 4, N001-N050 ------------------------------------------------------------------------------------------------
HEAD_D = r"^EVENT N\d{3}\s+-\s+"

# num: ({role: spec}, description, opts)
# opts: eff {k: [effects]}, to {k or 0: [text_only]}, instr {k: None (whole line) | text cut}, w {k: (weight, rarity)},
#       fix {k: (before, after)}, carers [roles: Parenting on every outcome]
D = {
    1: ({"teen": TEEN}, "A teenager samples farming, building, healing and research before choosing a path.",
        {"eff": {1: [c.skill("teen", FOUR)], 2: [like("teen", "work", "dislikes")]},
         "instr": {1: "; gain a small skill boost", 2: "; update a preference"}}),
    2: ({"teen": TEEN, "elder": EL}, "A teenager's family expects them to follow a respected trade.", {}),
    3: ({"teen": TEEN}, "A teen attempts a different specialty every day.", {}),
    4: ({"teen": TEEN}, "A teenager admires healers but struggles with the sight of injuries.",
        {"eff": {2: [like("teen", "herbs")]},
         "to": {0: [T("injuries", "the sight of injuries in general; nobody is hurt")]}}),
    5: ({"teen": TEEN}, "A teen training as a builder spends more time making music.",
        {"eff": {1: [bld("teen")]},
         "to": {1: [T("both skills", "music is no game skill (rule 8): only Building is gained")]}}),
    6: ({"teen": TEEN, "mentor": V}, "A teen's first public demonstration goes terribly wrong.", {}),
    7: ({"teen": TEEN, "sibling": c.related(c.ANY_AGE, "sibling_of", "teen"), "friend": V},
        "A young villager feels inferior to a talented sibling.",
        {"to": {2: [T("a new skill", "trying a skill; no gain is stated")]}}),
    8: ({"teen": TEEN}, "Masters from several disciplines demonstrate their work to teenagers.",
        {"to": {0: [T("masters", "the masters are text figures; nobody's skill is set")]}}),
    9: ({"cook": V, "child": CH}, "A cook experiments with concentrated fruit syrup and edible seeds.", {}),
    10: ({"chef": V}, "A chef combines unfamiliar island ingredients into a ceremonial dish.", {}),
    11: ({"cook1": V, "cook2": V}, "Two cooks compete to make the crispest snack.", {}),
    12: ({"confectioner": V}, "A confectioner struggles to keep a delicate sweet intact in the tropical heat.", {}),
    13: ({"cook": YOUNG_COOK}, "A young cook tries to recreate a deceased relative's signature dish.", {}),
    14: ({"child": CH, "chef": V}, "A curious child samples a dish before the feast.", {}),
    15: ({"baker": V}, "A villager begins making treats long after everyone sleeps.", {}),
    16: ({"cook": V, "researcher": SCHOLAR}, "A cook creates a dish that looks awful but smells wonderful.", {}),
    17: ({"forager": V}, "A forager discovers a pale mushroom with a spiral stem.",
         {"instr": {2: None},
          "to": {2: [T("movement animation reverses", "rule 9: no game reverses a villager's walk")]}}),
    18: ({"villager": V}, "A bright fungus seems to alter how its eater speaks.", {}),
    19: ({"villager": V}, "A mushroom's spores leave a startling stain.",
         {"eff": {1: [{"do": "appearance", "role": "villager", "head": "random"}]}, "instr": {1: None},
          "to": {2: [T("purple hair until washed", "rule 9: no head is purple, and the stain washes out")]}}),
    20: ({"villager": V}, "An edible-looking fungus triggers inexplicable strong preferences.",
         {"instr": {1: None, 2: None},
          "to": {1: [T("a random valid like", NO_RANDOM_PREF)], 2: [T("a random valid dislike", NO_RANDOM_PREF)]}}),
    21: ({"researcher": SCHOLAR}, "A researcher studies a fungus associated with unusual alertness.",
         {"eff": {1: [res("researcher")]}, "instr": {1: None, 2: None},
          "to": {2: [T("a temporary concentration penalty", "rule 9: no game has a concentration penalty")]}}),
    22: ({"villager": V}, "A peculiar mushroom seems to interfere with coordination.",
         {"eff": {1: [loss("villager", EVERY_SKILL)]}, "instr": {1: None}}),
    23: ({"forager": V, "naturalist": SCHOLAR}, "A forager mistakes a poisonous species for a familiar edible mushroom.",
         {"eff": {1: [{"do": "sick", "role": "forager"}], 2: [{"do": "kill", "role": "forager", "cause": "unknown"}]},
          "instr": {2: " if the fatal branch is enabled"}, "w": {1: (5, "rare"), 2: (5, "rare")},
          "fix": {2: ("villager dies", "the villager dies")}}),
    24: ({"researcher": SCHOLAR, "child": CH}, "A circle of fungi appears overnight in a clearing.",
         {"eff": {1: [res("researcher")]}}),
    25: ({"villager": V}, "A villager claims a strange mushroom brought back a vivid childhood memory.", {}),
    26: ({"villager": V}, "An apparent fungus turns out to be something else entirely.", {}),
    27: ({"musician": V, "child": CH}, "A musician stretches animal-hair strings across a carved resonating shell.", {}),
    28: ({"builder": BUILDER, "elder": EL}, "Builders discover a fallen tree with remarkable resonance.", {}),
    29: ({"artisan": V}, "An artisan fills woven seed pods with dried pebbles.", {}),
    30: ({"musician": V, "apprentice": V}, "A musician drills carefully spaced openings in a hollow reed.", {}),
    31: ({"musician": V, "listener": V}, "A village ensemble attempts an ambitious performance.", {}),
    32: ({"singer": V, "friend": V}, "A villager with a beautiful voice refuses to perform publicly.", {}),
    33: ({"archer": V, "learner": V}, "A skilled archer teaches novices using straw targets and blunt practice arrows.",
         {}),
    34: ({"archer": V, "trainee": V}, "An archer must decide between showing off and helping a struggling trainee.", {}),
    35: ({"practitioner": V, "drummer": V}, "Combat-art practitioners synchronize ceremonial defensive steps to drumbeats.",
         {}),
    36: ({"artisan": V}, "An artisan makes a ceremonial bow from flexible wood and woven fibers.", {}),
    37: ({"healer": HEALER, "colleague": V}, "A healer finishes a day caring for severely injured villagers and feels overwhelmed.",
         {"to": {0: [T("severely injured villagers", "the day's past patients; nobody is hurt now")]}}),
    38: ({"mentor": HEALER, "trainee": V}, "An experienced healer says that one must simply deal with it.", {}),
    39: ({"trainee": V}, "A trainee is unsettled while learning anatomy from someone who has died.", {}),
    40: ({"healer": HEALER}, "A healer cannot stop thinking about a patient who died.", {}),
    41: ({"healer": HEALER, "patient": V}, "After a difficult series of cases, a healer watches a patient recover.",
         {"eff": {2: [{"do": "celebrate", "who": "healer"}]}}),
    42: ({"healer": HEALER}, "A healer accidentally says something insensitive to a grieving family.", {}),
    43: ({"healer": HEALER}, "Villagers expect a master healer to know every answer.", {}),
    44: ({"healer": HEALER, "retired": RETIRED_HEALER}, "Healers establish a quiet place to speak after hard days.", {}),
    45: ({"villager": G}, "Villagers discuss establishing a home for children without available caregivers.", {}),
    46: ({"child": CH, "caregiver": G}, "A recently orphaned child is shown a place to sleep in a new home.",
         {"carers": ["caregiver"]}),
    47: ({"carer": G, "apprentice": V}, "A childcarer is exhausted while caring for several babies and toddlers.",
         {"carers": ["carer"], "eff": {2: [c.parenting("apprentice")]}}),
    48: ({"pupil": CH}, "A pupil refuses to participate in lessons.", {}),
    49: ({"child": CH, "teacher": G}, "A child interrupts every lesson, insisting they already know everything.",
         {"carers": ["teacher"]}),
    50: ({"child": CH, "friend": CH, "adult": G}, "A child secretly takes a friend's treasured object.",
         {"eff": {3: [c.parenting("adult")]}}),
}

# ---- Part 5, V031-V050 ------------------------------------------------------------------------------------------------
HEAD_E = r"^EVENT V\d{3}\s+-\s+"
E = {
    31: ({"dancer": V, "friend": V}, "A shy villager invents a dance alone on the beach.", {}),
    32: ({"musician": V}, "A musician wants to impress the entire village but dislikes the popular songs.",
         {"to": {0: [T("dislikes", "a taste in songs; songs are no game preference (rule 8)")]}}),
    33: ({"villager": V}, "A thoughtful villager is nominated to lead a work group despite rarely speaking.", {}),
    34: ({"builder": BUILDER, "apprentice": V}, "A bold builder makes a public mistake while a cautious apprentice succeeds.",
         {}),
    35: ({"villager": V, "friend": V}, "A villager fears their closest friend will fail at a new profession.", {}),
    36: ({"villager": V}, "A villager wakes feeling low without knowing why.", {}),
    37: ({"villager": V, "other": V}, "A physically weak villager proves exceptional at patient, intricate work.", {}),
    38: ({"villager": V}, "A work crew lets a different member coordinate each day.", {}),
    39: ({"leader": G}, "A new leader must choose between an impressive monument and repairing essential shelters.", {}),
    40: ({"villager1": V, "villager2": V}, "Two families with a long-standing disagreement are paired during a festival dance.",
         {}),
    41: ({"villager": V}, "A spring flows again after a devotional ceremony and a season of heavy rain.", {}),
    42: ({"farmer": FARMER}, "An orchard is failing and villagers disagree over magical, spiritual or ecological remedies.",
         {"instr": {2: " where the game supports it"},
          "to": {2: [T("a magical intervention", "rule 9: the magic is told, never made")]}}),
    43: ({"builder": BUILDER}, "A builder wants timber from a grove revered by another community.", {}),
    44: ({"villager": V}, "A wild animal repeatedly visits the village food stores.",
         {"to": {0: [T("food", "the animal visits the stores; no food is lost or gained")]}}),
    45: ({"villager": V}, "Travelers from another island community arrive with unfamiliar customs.", {}),
    46: ({"villager": V}, "Two communities disagree over access to fresh water.", {}),
    47: ({"elder": EL}, "An elder remembers a dispute with another tribe that younger villagers barely understand.", {}),
    48: ({"child": CH, "elder": EL, "researcher": SCHOLAR},
         "A child asks why the gods or spirits never answer in a way everyone can hear.", {}),
    49: ({"villager": V}, "Some villagers consider a rare fish spiritually significant while others see it as food.",
         {"to": {0: [T("food", "a belief about the fish; no food is caught or lost")]}}),
    50: ({"mentor": V}, "An outsider asks to join the village permanently.", {}),
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


def outcomes(row, opts, lines, ledger, fixes) -> dict:
    """One node per outcome line: the shown text appended to the setup's popup, or a silent node for an instruction."""
    nodes = {}
    eff, tonly, instr, fix = opts.get("eff", {}), opts.get("to", {}), opts.get("instr", {}), opts.get("fix", {})
    carers = opts.get("carers", [])
    for k, n in enumerate(lines, 1):
        cuts = []
        raw = c.line(n)
        m = TAG_RE.match(raw)
        if m:
            ledger.append({"src": c.L(n), "kind": "note", "text": m.group(1) + ":",
                           "why": "a designer tag on the outcome, never shown"})
            cuts.append(m.group(1) + ":")
        effects = [c.parenting(r) for r in carers] + eff.get(k, [])
        name = f"Outcome {k}" if len(lines) == 3 else f"Outcome {chr(64 + k)}"
        if k in instr and instr[k] is None:
            ledger.append({"src": c.L(n), "kind": "instruction",
                           "why": "the outcome is a mechanical instruction, never shown: the node carries its "
                                  + ("effect" if eff.get(k) else "text_only reason")})
            node = {"type": "branch", "name": name}
            if effects:
                node["effects"] = c.with_src(effects, c.L(n))
            if tonly.get(k):
                node["text_only"] = c.with_src(tonly[k], c.L(n))
            nodes[f"e{k}"] = node
            continue
        if k in instr:
            ledger.append({"src": c.L(n), "kind": "instruction", "text": instr[k],
                           "why": "an instruction inside the outcome, never shown: "
                                  + ("the node's effect" if eff.get(k) else "its text_only reason")})
            cuts.append(instr[k])
        fx = {}
        if k in fix:
            fixes.append({"src": c.L(n), "before": fix[k][0], "after": fix[k][1]})
            fx = {n: [fix[k]]}
        with c.lib.use_source(c.lib.COMPANION_ID):
            text = c.cc.processed_line(n, {n: cuts}, fx)
        text = text[:1].upper() + text[1:]
        nodes[f"e{k}"] = c.page(name, text, c.L(n), effects, tonly.get(k, ()), append=True)
    return nodes


def children(opts, count) -> list[dict]:
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
    nodes = {"setup": {"name": "The setup", "text": c.shown(setup), "src": c.L(setup),
                       "children": children(opts, 3)}}
    if opts.get("to", {}).get(0):
        nodes["setup"]["text_only"] = c.with_src(opts["to"][0], c.L(setup))
    nodes.update(outcomes(row, opts, [h + 3, h + 4, h + 5], ledger, fixes))
    extra = {"grammar_fixes": fixes} if fixes else None
    return finish(row, h, title, ledger, desc, roles, nodes, "setup", extra)


def build_e(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, opts = E[num]
    h = c.heading_line(row, HEAD_E)
    title = re.split(HEAD_E, c.line(h), maxsplit=1)[1].strip()
    setup, oa, ob, note = h + 1, h + 2, h + 3, h + 4
    assert c.line(setup).startswith("SETUP:") and c.line(oa).startswith("OUTCOME A:"), row["id"]
    assert c.line(ob).startswith("OUTCOME B:") and c.line(note).startswith("CHOICE: Optional;"), row["id"]
    assert note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "CHOICE: Optional; a designer note: the event is observational, one outcome is drawn"})
    nodes = {"setup": {"name": "The setup", "text": c.shown(setup), "src": c.L(setup),
                       "children": children(opts, 2)}}
    if opts.get("to", {}).get(0):
        nodes["setup"]["text_only"] = c.with_src(opts["to"][0], c.L(setup))
    fixes: list = []
    nodes.update(outcomes(row, opts, [oa, ob], ledger, fixes))
    return finish(row, h, title, ledger, desc, roles, nodes, "setup")


# ---- V060, How Did We Get Here? (L3690-3742) --------------------------------------------------------------------------
V060_ACCOUNTS = {1: (3697, [(3698, 3699), (3700, 3700), (3701, 3701)]),
                 2: (3703, [(3704, 3705), (3706, 3706), (3707, 3708)]),
                 3: (3710, [(3711, 3711), (3712, 3712), (3713, 3713)]),
                 4: (3716, [(3717, 3718), (3719, 3719), (3720, 3720)]),
                 5: (3722, [(3723, 3723), (3724, 3724), (3725, 3725), (3726, 3726)])}
V060_NOTE_CUT = "These are remembered stories, hypotheses and legends,"


def joined(a: int, b: int, cuts: dict | None = None) -> str:
    """Lines a..b as one paragraph: only its first letter may change case."""
    with c.lib.use_source(c.lib.COMPANION_ID):
        text = " ".join(c.cc.processed_line(n, cuts or {}, {}) for n in range(a, b + 1)).strip()
    return text[:1].upper() + text[1:]


def build_v060(row: dict) -> dict:
    h = 3690
    assert c.line(h).startswith("EVENT V060") and row["lines"] == [3690, 3742], row
    cuts = {3693: [V060_NOTE_CUT]}
    setup_text = joined(3692, 3693, cuts)
    ledger = [{"src": "L3693", "kind": "note", "text": V060_NOTE_CUT,
               "why": "the designer's framing of the accounts, never shown"},
              {"src": "L3694-3695", "kind": "note", "why": "the designer's rule: show only this game's accounts"}]
    for g, (head, _) in V060_ACCOUNTS.items():
        ledger.append({"src": c.L(head), "kind": "structural", "why": f"the game heading: the accounts shown in VV{g}"})
    ledger += [{"src": "L3714", "kind": "note", "why": "a designer note on The Secret City's tribes, never shown"},
               {"src": "L3728", "kind": "structural", "why": "the player options' heading"},
               {"src": "L3733", "kind": "structural", "why": "the outcomes' heading: one is drawn"},
               {"src": "L3740-3742", "kind": "note", "why": "IMPLEMENTATION: a designer note, never shown"}]
    labels = [{"label": c.shown(n), "next": "outcome", "src": c.L(n)} for n in (3729, 3730, 3731)]
    nodes: dict = {"origin": {"type": "branch", "name": "This game's accounts",
                              "children": [{"next": f"q{g}", "if": {"game": [g]}} for g in V060_ACCOUNTS]}}
    for g, (_head, accts) in V060_ACCOUNTS.items():
        paras = [joined(a, b) for a, b in accts]
        if g == 4:
            assert paras[0].startswith("Supposedly the Chief "), paras[0]
            paras[0] = paras[0].replace("the Chief", "{@chief}", 1)
        text = "\n".join([setup_text] + paras)
        src = ",".join(["L3692-3693"] + [c.L(a) if a == b else f"L{a}-{b}" for a, b in accts])
        node = {"type": "question", "name": "Where did we come from?", "text": text, "src": src,
                "choices": [dict(x) for x in labels]}
        if g == 4:
            node["text_only"] = c.with_src(
                [T("signs of collapse", "a legend of the ancestors' old home; no building collapses")], "L3717-3718")
        if g == 5:
            assert "among the Heathens" in text
            node["variants"] = [{"if": {"patch": "guardians_of_isola"},
                                 "text": text.replace("among the Heathens", "among the Isolans")}]
        nodes[f"q{g}"] = node
    nodes["outcome"] = {"type": "branch", "children": [{"next": f"o{k}"} for k in range(1, 6)]}
    for k, n in enumerate(range(3734, 3739), 1):
        eff = [res("researcher")] if n == 3735 else []
        nodes[f"o{k}"] = c.page(f"Outcome {k}", c.shown(n), c.L(n), eff)
    roles = {"child": CH, "elder": EL, "researcher": SCHOLAR}
    desc = "A child asks where the tribe came from: hear another version, search for evidence, or accept the unknown."
    extra = {"patches": ["guardians_of_isola"],
             "words": {"chief": {"3": "the Chief", "*": "the village leader"}}}
    return finish(row, h, "How Did We Get Here?", ledger, desc, roles, nodes, "origin", extra)


def main() -> int:
    rows_d = [r for r in c.rows("c5dn") if c.num_of(r) in D]
    rows_e = [r for r in c.rows("c5ev") if c.num_of(r) in E or c.num_of(r) == 60]
    assert len(rows_d) == len(D) == 50 and len(rows_e) == len(E) + 1 == 21, (len(rows_d), len(rows_e))
    docs = [(r["section"], r["id"], build_d(r)) for r in rows_d]
    docs += [(r["section"], r["id"], build_v060(r) if c.num_of(r) == 60 else build_e(r)) for r in rows_e]
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
