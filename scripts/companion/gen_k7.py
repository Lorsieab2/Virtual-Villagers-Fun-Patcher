"""Chunk K7: write the Companion Anthology's The Four Ways of Knowing, events 001-060 (companion L5417-6038), as
data/event_collection/companion/fwk/fwk<NNN>_<slug>.json, then format and check them.

THE SOURCE'S FORMAT (two parts; the volume's rules L5408-5412 and the Part III retrofit prompt L6040-6044 are notes
rows, never carried out: verbatim only, no "full choice-specific, non-template outcome branches").

Part I, Four Lenses (001-040, 10 lines each):
  EVENT NNN - TITLE / Premise: / A. MAGIC-ALIGNED - <sentence> / B. NATURE-ALIGNED - / C. SPIRITUAL-ALIGNED - /
  D. SCIENTIFIC-ALIGNED - / Possible resolution 1 (mundane): / 2 (ambiguous): / 3 (social): / Contextual consequences:
- The premise is the question page.  Each lens line is one choice: its lens name is the button ("MAGIC-ALIGNED", shown
  "Magic-aligned" by the sentence-case rule, cie-v6-binary.md 20; the whole line is too wide for a button) and its
  sentence is that answer's page (inventory Q4's default).  The four lenses are never ranked (L5408): every lens
  leads to the same three resolutions, equally likely, appended to its page.  The owner (2026-11-15): the grief and
  loss events 009, 010, 013, 038, 039 and 040 use only resolutions 2 and 3 (resolution 1 could read as minimizing;
  its line is unchanged, a ledger note records it as unused).
- THE POOL DECISION: the three "Possible resolution" lines are repeated word for word in all 40 events, but each event
  has its OWN copy on its own lines, every one of which must be consumed by that event.  A whole page chosen at random
  is a branch, not a pool (a pool inserts text inside a sentence); a shared pool in shared_pools.json would leave each
  event's own lines unconsumed and needs a companion source in check_shared_pools() (companion-authoring.md 9).  So
  each event writes the resolutions inline: a branch of three equal append pages, src'd to its own lines.  No pool.
- "Possible resolution n (tag):" is a designer tag (a ledger note cut); "; no school is confirmed or mocked" (every
  resolution 2) is the designer's instruction to the writer (a ledger instruction cut, inventory section 4).

Part II, Work, Age, Fear, and Grave Mistakes (041-060, 8 lines each):
  EVENT NNN - TITLE / Premise: / A.-D. four concrete choices / Possible outcomes: / Contextual consequences:
- The premise is the question page; the four choices have no outcome of their own, so every label leads to the
  event's one ending, "Possible outcomes:" (a designer tag cut), as companion-authoring.md section 4 maps it.  Where a
  label itself states a consequence the game can show, that label leads to its own copy of the ending carrying the
  effect (as gen_k8's split copies its page).

CASTING: the text names nobody (rule 10); every role is cast so the scene's people exist, and a role no effect uses
is in collection.cast_only.  Elders 55+ ("an elder", "aging", "veteran"), a child 3-13, anyone else 14+; trades the
text names as qualifications are skilled roles (a healer, a researcher, a farmer, a builder, a scholar).  053's
nursing mother is a female nursing parent.  No magician acts anywhere in this volume: every event is in all 5 games
(priests, festivals and gods are text figures, as in the inventory).

EFFECTS (V28 consequence rules: only where the text clearly supports one):
- Part I: none.  Each lens page is an interpretation, and a reward for one lens would rank it above the others
  (L5408 "not alignment tests or moral rankings").  The resolutions are generic.
- Part II, from the label's own words: 042 D "Invent a safer method" the builder's small Building; 046 C "Find them
  injured" the apprentice's minor injury (health_change -30..-10), 046 D "Face an unresolved disappearance" the
  apprentice vanishes (missing, no grave: the game's vanish is permanent); 047 C "Repeat the experiment and learn why
  it failed" the scholar's small Research; 051 A "Try the look" the villager's head, random (gen_k8 052); 053 C
  "Overextend herself and become ill" the nursing mother falls sick (protected allow, retrofit-harm-review.md);
  055 C "develop a dislike of the craft" a dislike of work (the craft is the craftsperson's work).
- Text only (rules 7-9): reputations, trust, professions, apprenticeships, fashion trends, accidents with no one
  named hurt, a new preference the text does not name (gap C1), memories and callbacks.

SENSITIVITY: none.  The owner (2026-11-15): keep the text exactly; reword only what the owner has named (angels,
demons, legendary beings, afterlife, cannibals, headhunters).  None of those is named in this volume ("unseen
guardians", "guiding lights", "hope for reunion" are hints, as the rules ask), so 005 D "recordings" stays.

    python scripts/companion/gen_k7.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

cc, lib = c.cc, c.lib
V, G, CH, EL = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")
FARMER = c.skilled(V, "Farming")
BUILDER = c.skilled(V, "Building")
NURSING = {"kind": "villager", "min_age": 18, "special": "nursing_parent", "protected": "allow"}
T = c.text_only
HEAD = r"^EVENT \d{3}\s+-\s+"
LENSES = ("MAGIC-ALIGNED", "NATURE-ALIGNED", "SPIRITUAL-ALIGNED", "SCIENTIFIC-ALIGNED")
RES_TAGS = ("Possible resolution 1 (mundane):", "Possible resolution 2 (ambiguous):",
            "Possible resolution 3 (social):")
DESIGNER = "; no school is confirmed or mocked"
MODERN = "rule 3 (2026-11-14): a modern-day thing in the words of people who never saw one"
# The owner (2026-11-15): grief and loss events where resolution 1 ("may still value the experience") could read as
# minimizing keep only resolutions 2 and 3; the line stays in the source, recorded in the ledger as unused.
NO_RES1 = (9, 10, 13, 38, 39, 40)
EXPERIENCE = T("the experience", "a memory of what happened, not a skill's experience: nothing is gained")

# num: ({role: spec}, description, opts)
# opts: to {0 (premise) | "a".."d" (a lens page) | "r1".."r3" | "out" (Part II ending): [text_only]},
#       eff {"a".."d": [effects]} (Part II: the label's own consequence, on its own copy of the ending),
#       sens {line offset from the heading: [(before, after)]}
D = {
    1: ({"villager": V}, "A villager keeps sensing a presence at the forest's edge, though nobody is ever there.", {}),
    2: ({"villager": V}, "The shoreline seems to expand and contract in a rhythm a villager cannot ignore.", {}),
    3: ({"villager": V}, "A villager has a vivid sense of having already lived through a conversation.", {}),
    4: ({"dreamer1": V, "dreamer2": V}, "Two villagers describe remarkably similar dreams of a stone doorway.", {}),
    5: ({"villager": V}, "A villager hears what sounds like their own name carried by the surf.", {}),
    6: ({"villager": V}, "After heavy rain, a familiar trail seems to lead somewhere different.", {}),
    7: ({"elder": EL, "relative": V}, "A sapling grows beside the spot where an elder once told stories.", {}),
    8: ({"villager": V}, "A rock gives off a faint sound when the sun warms it.", {}),
    9: ({"villager": V}, "A villager prays for a sick friend, but the illness worsens.",
        {"to": {"b": [T("food", "food and care given to the friend; the village's food does not change")]}}),
    10: ({"survivor": V, "neighbor": V},
         "A storm wrecks a generous family's home but spares an unkind neighbor's hut.", {}),
    11: ({"villager": V}, "A strange object washes ashore, hinting at lands beyond the horizon.", {}),
    12: ({"villager": V}, "A villager wonders whether the island protects its people or keeps them from leaving.", {}),
    13: ({"villager": V},
         "After a tragedy, a villager asks whether any divine power cares about ordinary suffering.", {}),
    14: ({"child": CH, "healer": HEALER},
         "A child recovers unexpectedly after several villagers tried different remedies.", {}),
    15: ({"fisher": V}, "A fisher hears no birds or insects for an entire morning.", {}),
    16: ({"child": CH, "adult": G}, "A child believes the moon follows them wherever they walk.", {}),
    17: ({"villager": V, "neighbor": V}, "An omen predicts a disaster, but nothing happens.", {}),
    18: ({"child": CH, "parent": G}, "A child who was present at several accidents fears they bring bad luck.", {}),
    19: ({"villager": V}, "A villager sees an unfamiliar expression in their reflection in still water.", {}),
    20: ({"villager": V, "leader": G}, "A ceremonial fire keeps failing to light, upsetting the gathering.", {}),
    21: ({"villager": V}, "A villager makes a difficult decision just as the first rain begins.", {}),
    22: ({"healer": HEALER, "steward": V}, "A grove gives medicinal plants but is also revered as sacred.", {}),
    23: ({"villager": V}, "A flood shifts the riverbank, exposing a family's old gathering place.", {}),
    24: ({"villager": V, "neighbor": V}, "A deep rumble beneath the island alarms the villagers.", {}),
    25: ({"child": CH, "mentor": G}, "A child asks why adults call some events miracles and others accidents.", {}),
    26: ({"elder": EL}, "An elder admits that a belief held for decades no longer feels certain.", {}),
    27: ({"villager": V}, "A cave echoes with a pulse-like thud.", {}),
    28: ({"cartographer": V}, "A young cartographer asks whether any map can truly contain Isola.", {}),
    29: ({"explorer": V}, "An explorer can reach an ancient inscription only by crossing dangerous ground.", {}),
    30: ({"performer": V, "farmer": FARMER}, "A major festival passes without any of the customary omens.",
         {"to": {"b": [T("celebrates", "one farmer's own celebration of the harvest, not the village's")]}}),
    31: ({"maker": V, "steward": V}, "Two families quarrel over a windy hill that suits both sails and ceremonies.", {}),
    32: ({"gardener": FARMER}, "Seedlings stand unusually tall after a warm, wet night.", {}),
    33: ({"diver": V}, "A diver sees an eerie glow moving beneath the reef.", {}),
    34: ({"villager": V}, "A villager finds their name carved into an old wall from before they were born.", {}),
    35: ({"witness1": V, "witness2": V}, "Two witnesses describe the same event in contradictory ways.", {}),
    36: ({"farmer1": FARMER, "farmer2": FARMER},
         "One farmer works tirelessly and harvests little, while another works less and harvests plenty.", {}),
    37: ({"villager": V}, "A newcomer knows details of a local legend that nobody remembers telling them.", {}),
    38: ({"survivor": V}, "After a shipwreck, useful supplies and a treasured family object wash ashore together.", {}),
    39: ({"villager": V}, "A villager asks what happens after death and hears four different answers.",
         {"to": {0: [T("death", "a question about death; nobody dies")]}}),
    40: ({"mourner": V, "relative": V}, "During a vigil, a candle burns much longer than expected.", {}),
    41: ({"healer": c.skilled(EL, "Healing"), "apprentice": V},
         "An aging healer notices their hands shake during delicate work.", {}),
    42: ({"builder": c.skilled(EL, "Building"), "climber": V},
         "An elder builder wonders whether climbing high scaffolds is still wise.",
         {"eff": {"d": [c.skill("builder", "Building")]}}),
    43: ({"researcher": SCHOLAR}, "A talented researcher dreads each morning at the laboratory.", {}),
    44: ({"fisher": V}, "After a frightening accident, a fisher cannot face the sea.", {}),
    45: ({"healer": HEALER, "patient": V}, "A distracted healer realizes a patient received the wrong preparation.",
         {}),
    46: ({"apprentice": V, "mentor": G}, "An apprentice disappears after a bitter argument with their mentor.",
         {"eff": {"c": [{"do": "health_change", "role": "apprentice", "min": -30, "max": -10}],
                  "d": [{"do": "vanish", "role": "apprentice"}]},
          "to": {0: [T("an apprentice vanishes", "the premise: on A and B the apprentice is found or comes back "
                                                 "unhurt; C and D are their own answers")]}}),
    47: ({"scholar": SCHOLAR, "assistant": V},
         "A scholar publicly announces a discovery that turns out to be mistaken.",
         {"eff": {"c": [c.skill("scholar", "Research")]}}),
    48: ({"farmer": FARMER}, "A skilled farmer dreams of becoming an astronomer.", {}),
    49: ({"villager": V}, "A soft-spoken villager is nominated to lead a loud, argumentative group.", {}),
    50: ({"explorer": V, "companion": V}, "An explorer ignores a safety signal and puts a companion in danger.", {}),
    51: ({"tailor": V, "villager": V}, "A tailor proposes a striking new style of clothing and hair for the village.",
         {"eff": {"a": [{"do": "appearance", "role": "villager", "head": "random"}]},
          "to": {"a": [T("gain a new preference", "the text names no like (gap C1): text only")]}}),
    52: ({"child": CH, "adult": G}, "A child begs to help with an adult task beyond their experience.",
         {"to": {0: [T("experience", "the child's lack of experience, not a skill change"),
                     T("cause an accident", "the text names nobody hurt in the accident: text only")]}}),
    53: ({"mother": NURSING}, "A nursing mother is asked to help during a village emergency.",
         {"eff": {"c": [{"do": "sick", "role": "mother"}]}}),
    54: ({"villager": V, "rival": V}, "A villager is invited to work with a former rival.", {}),
    55: ({"craftsperson": V}, "After a long illness, a craftsperson struggles with a technique once mastered.",
         {"eff": {"c": [{"do": "preference", "role": "craftsperson", "list": "dislikes", "preference": "work"}]}}),
    56: ({"villager": G}, "A villager wants to chase a risky ambition while their family depends on them.", {}),
    57: ({"builder": BUILDER}, "A builder learns that a shortcut they approved weakened a bridge.",
         {"to": {0: [T("an accident", "the text names nobody hurt and no structure lost: text only")]}}),
    58: ({"artisan": V, "elder": EL}, "A young artisan becomes more skilled than the elder who trained them.",
         {"to": {0: [T("celebrate", "the master's own pride in the student, not a village celebration")]}}),
    59: ({"villager": V}, "An unpleasant but necessary village task keeps being ignored.", {}),
    60: ({"sailor": EL}, "A veteran sailor wonders whether one more long journey is worth the danger.",
         {"to": {0: [T("risk an accident", "a risk named on a choice; nobody is hurt")]}}),
}


def used_roles(nodes: dict) -> set[str]:
    return {e["role"] for n in nodes.values() for e in n.get("effects", []) if e.get("role")}


def build(row: dict) -> dict:
    num = c.num_of(row)
    roles, desc, opts = D[num]
    assert c.description_ok(desc), (row["id"], desc, len(desc))
    h = c.heading_line(row, HEAD)
    premise = h + 1
    part1 = num <= 40
    note = h + (9 if part1 else 7)
    assert c.line(premise).startswith("Premise:"), row["id"]
    assert c.line(note).startswith("Contextual consequences:") and note == row["lines"][1], row["id"]
    ledger = c.group_heading_ledger(row, h)
    cuts: dict[int, list[str]] = {}
    fixes: dict[int, list[tuple[str, str]]] = {}
    for off, pairs in opts.get("sens", {}).items():
        for b, a in pairs:
            assert b in c.line(h + off), (row["id"], b)
            fixes.setdefault(h + off, []).append((b, a))
            ledger.append({"src": c.L(h + off), "kind": "sensitivity", "before": b, "after": a, "why": MODERN})
    tonly, eff = opts.get("to", {}), opts.get("eff", {})

    def shown(n: int) -> str:
        with lib.use_source(lib.COMPANION_ID):
            p = cc.processed_line(n, cuts, fixes)
        return p[:1].upper() + p[1:]

    nodes: dict = {}
    choices = []
    if part1:
        res = (h + 6, h + 7, h + 8)
        keep = (2, 3) if num in NO_RES1 else (1, 2, 3)
        for k, n in enumerate(res):
            assert c.line(n).startswith(RES_TAGS[k]), (row["id"], n)
            if k + 1 not in keep:
                ledger.append({"src": c.L(n), "kind": "note",
                               "why": "owner decision (2026-11-15): resolution 1 is not used in this grief or loss "
                                      "event, where it could read as minimizing; the text is unchanged"})
                continue
            cuts[n] = [RES_TAGS[k]]
            ledger.append({"src": c.L(n), "kind": "note", "text": RES_TAGS[k],
                           "why": "designer tag on the resolution (L5415: possible branches, not results)"})
        assert DESIGNER in c.line(res[1]), row["id"]
        cuts[res[1]].append(DESIGNER)
        ledger.append({"src": c.L(res[1]), "kind": "instruction", "text": DESIGNER,
                       "why": "the designer's instruction to the writer (L5408: no lens is confirmed or mocked)"})
        for i, k in enumerate("abcd"):
            n = h + 2 + i
            m = re.fullmatch(rf"({LENSES[i]}) - (.+)", shown(n))
            assert m, (row["id"], k, shown(n))
            choices.append({"label": m.group(1), "next": k, "src": c.L(n)})
            page = c.page(f"Answer {k.upper()}", m.group(2), c.L(n), (), tonly.get(k, ()))
            page["children"] = [{"next": f"r{j}"} for j in keep]
            nodes[k] = page
        for j, n in enumerate(res, 1):
            if j not in keep:
                continue
            extra = [EXPERIENCE] if j == 1 else []
            nodes[f"r{j}"] = c.page(f"Resolution {j}", shown(n), c.L(n), (), extra + list(tonly.get(f"r{j}", ())),
                                    append=True)
    else:
        out = h + 6
        tag = "Possible outcomes:"
        assert c.line(out).startswith(tag), row["id"]
        cuts[out] = [tag]
        ledger.append({"src": c.L(out), "kind": "note", "text": tag,
                       "why": "designer tag on the ending (the four choices have no outcome of their own)"})
        for i, k in enumerate("abcd"):
            n = h + 2 + i
            assert c.line(n).startswith(f"{k.upper()}. "), (row["id"], k)
            target = f"outcome_{k}" if k in eff else "outcome"
            choices.append({"label": shown(n), "next": target, "src": c.L(n)})
            if k in eff:
                nodes[target] = c.page(f"Ending ({k.upper()})", shown(out), c.L(out), eff[k], tonly.get(k, ()))
        if any(k not in eff for k in "abcd"):
            nodes["outcome"] = c.page("Ending", shown(out), c.L(out), (), tonly.get("out", ()))
    ledger.append({"src": c.L(note), "kind": "note", "why": "Contextual consequences: a designer note, never shown"})
    q = {"type": "question", "name": "The premise", "text": shown(premise), "src": c.L(premise), "choices": choices}
    if tonly.get(0):
        q["text_only"] = c.with_src(tonly[0], c.L(premise))
    nodes = {"premise": q, **nodes}
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in used_roles(nodes)]
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": c.ALL, "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "premise", "nodes": nodes}


def main() -> int:
    rows = c.rows("fwk")
    assert len(rows) == len(D) == 60, (len(rows), len(D))
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
