"""Chunk K8: write the Companion Anthology's Stone, Spirit, Strangers & Ordinary Lives, events 001-067 (companion
L6069-6757), as data/event_collection/companion/sss/sss<NNN>_<slug>.json, then format and check them.  The volume's
second part (The Inner Lives of Isola, 068-097) is chunk K9's.

THE SOURCE'S FORMAT (L6067: "Premise; A/B/C player choices and authored outcomes; context tags. Outcomes are
alternatives, not simultaneous facts."):
  [group heading between ===== lines] / EVENT NNN: Title / Premise: / A. label / Outcome: / B. / Outcome: / C. /
  Outcome: / Context and callbacks: (tags; a designer note)
- A true 1:1 choice: the premise is the question page with the three labels, and each label leads to its own answer
  page (the outcome line).  "Premise:", "A." and "Outcome:" are structural markers; the group headings are structural
  ledger entries; "Context and callbacks:" is a designer note.
- The volume's integration notes (L6055-6067) and expansion prompt (L6759-6765) are notes rows, never carried out
  (verbatim only: no "event-specific alternate result per choice").

CASTING (the lead's decisions, 2026-11-14):
- Elders 55+; "a toddler" / "a young child" 3-7; "a young villager" 3-17; a teen 14-17; a young adult 18-25; a child
  3-13; an adult 18+; anyone else 14+.  Trades the text names are skilled roles (a healer, a researcher, a farmer).
- Same-sex couples (007 two women, 008 two fathers, 014 two elderly women): two villagers of that sex; the
  relationship is text only (no game records one).  008's child has no parent link (two men cannot be its recorded
  parents).
- Non-binary or gender-diverse villagers (006, 015, 052): text, a villager of either sex; the text uses no he/she
  token for them.
- Disability and difference (001-005, 010-012): text only, no cure and no harm from it.
- A magician is a text figure; an event where a magician acts (032, 043, 045) is VV3-VV5 only, as magic is VV3-VV5
  lore (the lead, 2026-11-14; collection_manifest.COMPANION_GAMES).
- Outsiders, castaways, visitors and Biggles are text; ocean voyages
  beyond Isola are text (028 keeps to a nearshore trial).  An event whose people are all text casts one harmless
  villager the scene needs (gap G7).
- A deceased loved one in a premise stays generic text (gap C3: 041, 061, 064).

EFFECTS (V28 consequence rules: only where the outcome's own text clearly supports one; most outcomes are flavor):
- Skills: 008 B both fathers' small Parenting (the routine that works for the child); 010 A the teen's small
  Farming ("Demonstrations and labeled specimens help the teen thrive" -- a teen who "understands plants"); 020 A the
  jeweler's small Research ("Small controlled tests"); 040 A the healer's small Healing (triage); 042 A the
  naturalist's small Research ("Observations reveal"); 045 A the researcher's small Research ("Researchers find a
  physical response"); 047 A the builder's small Building ("Build a small prototype"); 049 A the researcher's small
  Research ("Early observations"); 059 A and C the parent's small Parenting (the child's own parent, child_of).
- Appearance: 052 C the friend's head, random ("Cut or restyle the hair ... A new look sticks"); A's green hair is
  text (no head is green, and the trend is brief).
- Harm: 018 C "may injure or kill an involved worker": the outcome's own alternatives, split by weight -- unhurt
  (20), a serious injury (rare, 5: health_change -60..-40) or a death (very rare, 2: kill, Unknown causes); the
  worker keeps protected "auto".  020 C "Several workers cough": the worker falls sick (sick).
- 065 The Nursing Mother's Loss (the lead, 2026-11-14): the infant has ALREADY died, as part of the premise, so the
  mother is an adult woman who need not be nursing (no special, no allow) and the baby is text only.  No harm.
- Words the effects table reads that change nothing get text_only with the reason (011 "injured workers", 015 "A
  village celebration", 018 "collapse", 032 "The fruit disappears", 037 "vanished", 040 "badly injured animal", 042
  "an old injury", 062 "may cause injury", 066 "vanished").
- Rules 7-9 (traditions, councils, reputations, trust, memories, later events, Navigation / Dance / Craft / Pottery /
  Mining / Jewelry): text only.

    python scripts/companion/gen_k8.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

V, G, CH, EL, TEEN = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN
YOUNG = {"kind": "villager", "min_age": 3, "max_age": 17}          # "a young villager", "a boy"
TODDLER = {"kind": "villager", "min_age": 3, "max_age": 7}         # "a young child"
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")                                 # a researcher, a naturalist
FARMER = c.skilled(V, "Farming")
BUILDER = c.skilled(V, "Building")
WOMAN = c.sexed(G, "female")
MAN = c.sexed(G, "male")
OLD_WOMAN = c.sexed(EL, "female")
NURSING = {"kind": "villager", "min_age": 18, "sex": "female", "special": "nursing_parent"}

MAGIC = [3, 4, 5]                                                  # a magician acts: magic is VV3-VV5 lore (lead)
T = c.text_only
HEAD = r"^EVENT \d{3}:\s+"


def sk(role: str, skill: str) -> dict:
    return c.skill(role, skill)


def hurt(role: str, lo: int, hi: int) -> dict:
    return {"do": "health_change", "role": role, "min": lo, "max": hi}


# num: ({role: spec}, description, opts)
# opts: eff {"a"|"b"|"c": [effects]}, to {0 (premise)|"a"|"b"|"c": [text_only]}, split {"c": [(weight, rarity,
#       [effects], [text_only]), ...]} -- one answer's own alternatives, each a copy of its page
D = {
    1: ({"cartographer": G, "apprentice": V},
        "A blind cartographer who knows the shoreline by sound and touch is doubted by a visiting apprentice.", {}),
    2: ({"teen": TEEN, "friend": V}, "A deaf teen loves the festival but cannot follow the drummer's shouted cues.", {}),
    3: ({"craftsperson": G, "coworker": V},
        "A one-handed craftsperson wants commissions, not pity, and an intricate clasp needs making.", {}),
    4: ({"healer": HEALER, "colleague": V},
        "An experienced healer forgets patients' names, and a younger colleague corrects them in public.", {}),
    5: ({"child": CH, "friend": CH}, "A child covers their ears during a crowded feast and retreats behind a hut.", {}),
    6: ({"villager": YOUNG},
        "A young villager explains that neither man nor woman describes them, and wants a place in village life.", {}),
    7: ({"weaver": WOMAN, "sweetheart": WOMAN, "elder": EL},
        "A woman asks another woman to the lantern festival, and an elder mistakes them for sisters.", {}),
    8: ({"father1": MAN, "father2": MAN, "child": TODDLER, "neighbor": V},
        "Two fathers disagree about a young child's bedtime while a neighbor keeps assuming roles.",
        {"eff": {"b": [c.parenting("father1"), c.parenting("father2")]}}),
    9: ({"villager": V, "friend": V}, "A sociable villager has missed several gatherings, and a friend worries.", {}),
    10: ({"teen": TEEN, "instructor": V},
         "A teen who understands plants well struggles with written instructions and is called careless.",
         {"eff": {"a": [sk("teen", "Farming")]}}),
    11: ({"elder": EL}, "An elder wants to attend a ceremony up a steep path, but their balance has worsened.",
         {"to": {"a": [T("injured workers", "the path is safer for anyone hurt; nobody is hurt now")]}}),
    12: ({"villager": V, "coworker": V},
         "A villager with chronic pain refuses a coworker's offers to carry their tools.", {}),
    13: ({"boy": c.sexed(YOUNG, "male")},
         "A quiet boy has a useful idea at a flood meeting but keeps being interrupted.", {}),
    14: ({"elder1": OLD_WOMAN, "elder2": OLD_WOMAN, "child": CH},
         "A child asks whether two elderly women who spend every evening together are best friends or sweethearts.",
         {}),
    15: ({"dancer": V}, "A nonbinary dancer asks to perform without being assigned to either group of dancers.",
         {"to": {0: [T("a village celebration", "the ceremony's custom is described; nobody celebrates on this "
                                                "page")]}}),
    16: ({"jeweler": V, "diver": V}, "A jeweler wants the shell of the season's only living conch for a horn.", {}),
    17: ({"jeweler": V}, "A red coral colony would make magnificent beads, but taking it may destroy years of growth.",
         {}),
    18: ({"miner": V, "worker": V}, "A miner sees a seam of silver behind unstable rock.",
         {"split": {"c": [
             (20, None, [], [T("a collapse damages equipment and may injure or kill",
                               "the collapse damages equipment, not a structure; on this branch nobody is hurt")]),
             (5, "rare", [hurt("worker", -60, -40)],
              [T("a collapse damages equipment", "the equipment, not a structure: only the worker is hurt")]),
             (2, "very_rare", [{"do": "kill", "role": "worker", "cause": "unknown"}],
              [T("a collapse damages equipment", "the equipment, not a structure: only the worker is hurt")])]}}),
    19: ({"diver": V}, "A diver finds a mollusk that may hold a pearl, but its kind is scarce.", {}),
    20: ({"jeweler": V, "worker": V}, "A jeweler wants to grind a staining blue mineral into pigment without knowing "
                                      "if the dust is safe.",
         {"eff": {"a": [sk("jeweler", "Research")], "c": [{"do": "sick", "role": "worker"}]}}),
    21: ({"apprentice": V}, "An apprentice melts down a family heirloom, believing it to be scrap metal.", {}),
    22: ({"miner": V}, "Miners find clean groundwater in a shaft, but digging farther may muddy the drinking supply.",
         {}),
    23: ({"partner1": G, "partner2": G},
         "A couple wants matching rings, but they disagree about precious metal and family tradition.", {}),
    24: ({"child": CH, "jeweler": G}, "A child finds a dazzling gem in a riverbed that a jeweler suspects is glass.",
         {}),
    25: ({"collector": V}, "A shell collector has promised more rare shells than the shoreline can supply.", {}),
    26: ({"jeweler": V}, "A jeweler finds a locket holding a tiny map drawn by an unknown hand.", {}),
    27: ({"miner": EL}, "A miner with aching joints wonders whether to keep working underground.", {}),
    28: ({"navigator": V}, "A navigator proposes crossing beyond the familiar horizon, and the village is divided.", {}),
    29: ({"villager": V}, "An unfamiliar canoe appears offshore, its passengers waving an object nobody recognizes.", {}),
    30: ({"villager": V}, "A visitor speaks unfamiliar words over a meal, and a villager wonders what they mean.", {}),
    31: ({"child": CH}, "A rescued child sings a lullaby nobody recognizes.", {}),
    32: ({"hunter": V, "child": CH}, "Odd footprints circle a hut overnight, and villagers disagree about Biggles.",
         {"games": MAGIC, "to": {"c": [T("the fruit disappears", "an offering of fruit; no villager disappears")]}}),
    33: ({"teen": TEEN}, "A teen's Biggles prank mask meets sightings the prank cannot explain.", {}),
    34: ({"villager": V}, "Three homes report identical knocks at the same moment on a windless night.", {}),
    35: ({"child": CH}, "A child who got lost in the woods says Biggles pointed the way home.", {}),
    36: ({"villager": V}, "A castaway asks to join the village but refuses to explain their past.", {}),
    37: ({"fisher": V, "elder": EL}, "A fisher swears a distant island appeared at dawn and vanished by noon.",
         {"to": {0: [T("an island vanished by noon", "a distant island seen at sea; no villager vanishes")]}}),
    38: ({"child": CH}, "A sign demands one coconut from every household for Biggles.", {}),
    39: ({"villager": V}, "A tiny unmanned boat washes ashore with unfamiliar knots and a flower tied to its bow.", {}),
    40: ({"healer": HEALER, "patient": V},
         "A healer has one clean dressing left for a villager and a badly injured animal.",
         {"eff": {"a": [sk("healer", "Healing")]},
          "to": {0: [T("a badly injured animal", "an animal is no villager; the villager already needs care, "
                                                 "nobody is hurt now")]}}),
    41: ({"relative": V}, "A family disagrees about a deceased scholar's wish that their body be used for study.", {}),
    42: ({"naturalist": SCHOLAR, "child": CH},
         "A dead sea turtle washes ashore: a naturalist wants to learn, a child wants a burial.",
         {"eff": {"a": [sk("naturalist", "Research")]},
          "to": {"a": [T("an old injury", "the dead turtle's; no villager is hurt")]}}),
    43: ({"farmer": FARMER}, "A magician claims credit for an astonishing harvest; farmers point to irrigation.",
         {"games": MAGIC}),
    44: ({"leader": G}, "A gifted leader wants authority to make emergency decisions without consultation.", {}),
    45: ({"researcher": SCHOLAR}, "A cave stone seems to vibrate when villagers sing nearby.",
         {"games": MAGIC, "eff": {"a": [sk("researcher", "Research")]},
          "to": {"c": [T("the experience", "a ceremony's experience, not a skill's: nothing is gained")]}}),
    46: ({"teen": TEEN, "elder": EL},
         "A thoughtful teen asks whether people can live good lives without believing in gods or spirits.", {}),
    47: ({"builder": BUILDER, "farmer": FARMER},
         "A water-lifting device would save hours of labor but needs materials and frequent repair.",
         {"eff": {"a": [sk("builder", "Building")]}}),
    48: ({"child": CH, "elder": EL, "researcher": SCHOLAR},
         "After a storm destroys a home, a child asks whether the gods were angry.", {}),
    49: ({"researcher": SCHOLAR, "healer": HEALER},
         "A researcher finds a substance that may treat illness but might also harm patients.",
         {"eff": {"a": [sk("researcher", "Research")]}}),
    50: ({"miner": V}, "A valuable ore deposit lies beneath a place important to several families.", {}),
    51: ({"villager": V}, "A villager feels watched by the forest and wonders whether Isola itself is alive.", {}),
    52: ({"teen": TEEN, "friend": V}, "A teen's berry dye turns friends' hair a startling shade of green.",
         {"eff": {"c": [{"do": "appearance", "role": "friend", "head": "random"}]},
          "to": {"a": [T("the hairstyle", "rule 9: no head is green, and the trend is brief")]}}),
    53: ({"jeweler": V, "parent": NURSING}, "A baby grabs a jeweler's necklace and scatters beads across the floor.",
         {}),
    54: ({"elder": EL, "potter": V}, "An elderly fisher confesses a lifelong wish to learn pottery.", {}),
    55: ({"coworker1": V, "coworker2": V}, "Two coworkers both claim the best seat under the shade tree.", {}),
    56: ({"villager": V, "friend": V},
         "A villager has carried an apology for years but cannot bring themselves to speak to an old friend.", {}),
    57: ({"researcher": SCHOLAR, "apprentice": V},
         "A proud researcher dismisses an apprentice's observation, only to find the apprentice was right.", {}),
    58: ({"villager": V, "friend": V},
         "A talkative villager assumes their quiet friend is upset because they rarely speak on walks.", {}),
    59: ({"parent": G, "child": c.related(CH, "child_of", "parent")},
         "A parent forgets a promised fishing trip with their child because of urgent village work.",
         {"eff": {"a": [c.parenting("parent")], "c": [c.parenting("parent")]}}),
    60: ({"healer": HEALER}, "A skilled healer no longer enjoys healing and would rather work with gemstones.", {}),
    61: ({"villager": V}, "A lantern goes out during a memorial: an omen, or a draft?", {}),
    62: ({"teen": TEEN}, "A reckless teen takes a dangerous shortcut to deliver supplies faster.",
         {"to": {"c": [T("a later event may cause injury or a missing-person search",
                         "rule 9: a later event; nobody is hurt or goes missing now")]}}),
    63: ({"cook": V, "elder": EL}, "An enthusiastic cook makes an enormous stew with an unfamiliar bitter vegetable.",
         {}),
    64: ({"villager": V, "relative": V},
         "A family disagrees about a memorial for someone who disappeared at sea.", {}),
    65: ({"mother": WOMAN}, "A nursing mother loses her infant, and the village struggles to support her.", {}),
    66: ({"teen": TEEN}, "A teenager missing on a coastal outing returns exhausted after two nights.",
         {"to": {0: [T("a teenager who vanished", "the teen has returned: nobody vanishes now")]}}),
    67: ({"baker": V}, "Nothing remarkable happens in the village today.", {}),
}


def used_roles(nodes: dict) -> set[str]:
    out = set()
    for n in nodes.values():
        for e in n.get("effects", []):
            r = e.get("role") or (e.get("who") if e.get("who") not in (None, "all") else None)
            if r:
                out.add(r)
    return out


def build(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, opts = D[num]
    assert c.description_ok(desc), (row["id"], desc)
    h = c.heading_line(row, HEAD)
    title = re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    premise, note = h + 1, h + 8
    assert c.line(premise).startswith("Premise:"), row["id"]
    assert c.line(note).startswith("Context and callbacks:") and note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "Context and callbacks: the designer's tags and notes, never shown"})
    eff, tonly, split = opts.get("eff", {}), opts.get("to", {}), opts.get("split", {})
    choices = []
    nodes: dict = {}
    for i, k in enumerate("abc"):
        lab, out = h + 2 + 2 * i, h + 3 + 2 * i
        assert c.line(lab).startswith(f"{k.upper()}. ") and c.line(out).strip().startswith("Outcome:"), (row["id"], k)
        choices.append({"label": c.shown(lab), "next": k, "src": c.L(lab)})
        name = f"Answer {k.upper()}"
        if k in split:
            kids = []
            for j, (w, rar, fx, to) in enumerate(split[k], 1):
                kid = {"next": f"{k}{j}", "weight": w}
                if rar:
                    kid["rarity"] = rar
                kids.append(kid)
                nodes[f"{k}{j}"] = c.page(f"{name} ({j})", c.shown(out), c.L(out), fx, to)
            nodes[k] = {"type": "branch", "name": name, "children": kids}
        else:
            nodes[k] = c.page(name, c.shown(out), c.L(out), eff.get(k, ()), tonly.get(k, ()))
    q = {"type": "question", "name": "The premise", "text": c.shown(premise), "src": c.L(premise),
         "choices": choices}
    if tonly.get(0):
        q["text_only"] = c.with_src(tonly[0], c.L(premise))
    nodes = {"premise": q, **nodes}
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in used_roles(nodes)]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": opts.get("games", c.ALL), "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "premise", "nodes": nodes}


def main() -> int:
    rows = [r for r in c.rows("sss") if c.num_of(r) in D]
    assert len(rows) == len(D) == 67, (len(rows), len(D))
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
