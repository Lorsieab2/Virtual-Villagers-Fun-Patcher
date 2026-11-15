"""Write the Companion Anthology's Volume 1 Part 1, Professional Specialties & Exploration (48 events, companion
L87-1114), as data/event_collection/companion/c5/c5a<NNN>_<slug>.json, then format and check them.

The source's format (every event, 17 lines; companion L81-84 "EVENT FORMAT"):
  EVENT 0NN - Title / Primary specialty: X / SETUP: <one sentence> / CHOICES: A-C (the same three labels in all 48)
  / RANDOM OUTCOME 1 - SUCCESS: ... / 2 - SETBACK: ... / 3 - SURPRISE: ... / FOLLOW-UP HOOK: (the same in all 48)
The specialty headings ("POTTERY" between rules) open the first event of each group.

How it maps (docs/event-collection/companion-authoring.md):
- The SETUP is the question page; the three choices are the source's own labels, each with its own src, and all three
  lead to the SAME outcome branch: "three alternative outcome seeds, not simultaneous results ... they are not fixed
  to particular choices" (L71, L82-84).  The three outcomes are equally likely (no odds given).
- "SUCCESS:", "SETBACK:", "SURPRISE:" are designer tags (ledger notes cut from the line); "RANDOM OUTCOME n -" is a
  structural marker.  "Primary specialty:", "CHOICES:", "FOLLOW-UP HOOK:" and the group headings are never shown.
- Effects (the part's rule L72, "Reward the principal discipline when appropriate", and the owner's V28 rules: only
  where the story clearly supports it, no reward inflation): the SUCCESS outcome gives the specialist a small skill in
  the game skill that IS their discipline (inventory Q9: Medicine and Potionmaking -> Healing; the sciences, History
  and Alchemy -> Research; a mechanist -> Building).  Pottery, Tribal Combat Arts, the exploration machines, weaving
  and the congress are no game skill: text only (rule 8), no effect.  Nobody is harmed in this part.
- The text names nobody (no placeholder): the specialist is cast so the reward lands (rule 10, a role with no token);
  a second person the setup names is cast too and listed in collection.cast_only.

    python scripts/companion/gen_c5a.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402

HEAD = r"^EVENT \d{3}\s+-\s+"
V, G = c.VILLAGER, c.GROWN
HEALER = c.skilled(c.VILLAGER, "Healing")

# num: ({role: spec} -- the first is the specialist, the rest only cast; skill of the SUCCESS reward or None;
#        description (Pick Island Event's sentence); {outcome 1-3 or 0 for the setup: [text_only]})
NOTE_COLLAPSE = c.text_only("collapse", "clay designs collapse, not a structure (no damage)")
E = {
    1: ({"potter": V}, None, "A potter tests clay, ash and crushed stone for vessels that survive fire and sea spray.", {}),
    2: ({"apprentice": V}, None, "An apprentice finds a clay pot that sings a low note whenever the wind crosses its rim.", {}),
    3: ({"potter1": V, "potter2": V}, None, "Two potters compete to make the most useful object from identical lumps of clay.",
        {2: [NOTE_COLLAPSE]}),
    4: ({"healer": HEALER}, "Healing", "A healer finds two nearly identical bottles: a familiar remedy and an experimental potion.", {}),
    5: ({"potionmaker": V}, "Healing", "A potionmaker sees an unusual colour shift in a mixture of fruit pigment and mineral extract.", {}),
    6: ({"apprentice": V}, "Healing", "An apprentice promises to brew a legendary potion before the next festival.", {}),
    7: ({"alchemist": V}, "Research", "An alchemist insists that ordinary beach sand can be turned into something precious.", {}),
    8: ({"alchemist": V}, "Research", "A forgotten alchemical cabinet holds an unmarked vial and a warning in an ancient script.", {}),
    9: ({"alchemist": V, "artisan": V}, "Research", "An alchemist spent the pigments promised to an artisan on experiments.", {}),
    10: ({"botanist": V}, "Research", "A botanist finds a plant whose leaves fold when touched.", {}),
    11: ({"botanist": V}, "Research", "A seed from an unknown shore takes root beside the village's oldest tree.", {}),
    12: ({"naturalist": V}, "Research", "A naturalist tries to preserve a sample of every known island plant.", {}),
    13: ({"researcher": V}, "Research", "A researcher looks at a drop of pond water through a newly polished lens.", {}),
    14: ({"researcher": V, "artisan": V}, "Research", "An artisan and a researcher build a magnifier from an unusually clear crystal.", {}),
    15: ({"healer": HEALER}, "Healing", "A healer wonders why clean-looking water sometimes spoils stored remedies.", {}),
    16: ({"chemist": V}, "Research", "A chemist compares plant extracts mixed with different mineral-rich waters.", {}),
    17: ({"researcher": V}, "Research", "A bowl of evaporating seawater leaves crystals of several shapes behind.", {}),
    18: ({"researcher": V}, "Research", "A careless collision overturns several jars of harmless coloured experimental liquids.", {}),
    19: ({"researcher": V, "builder": V}, "Research", "Builders and researchers argue about why differently shaped objects fall as they do.", {}),
    20: ({"researcher": V}, "Research", "A strange porous rock seems to float in a pool.", {}),
    21: ({"explorer": V}, "Research", "An explorer finds a cave where footsteps echo in a peculiar rhythm.", {}),
    22: ({"astronomer": V}, "Research", "An astronomer records the shadow of a tall pole at different times of day.", {}),
    23: ({"astronomer": V}, "Research", "Villagers report a bright object moving slowly among the stars.", {}),
    24: ({"scholar": V}, "Research", "A scholar predicts an unusual darkening of the sky.", {}),
    25: ({"mathematician": V}, "Research", "A mathematician finds a repeating pattern in woven mats and shell arrangements.", {}),
    26: ({"mathematician": V, "builder": V}, "Research", "A builder challenges a mathematician to estimate the materials for a bridge.", {}),
    27: ({"villager": V}, None, "Several families disagree about how to divide a communal harvest.", {}),
    28: ({"healer": HEALER}, "Healing", "A healer sees two villagers with similar symptoms but very different histories.", {}),
    29: ({"apprentice": V}, "Healing", "A nervous medical apprentice must assess an injured villager under a master's eye.",
         {0: [c.text_only("injured", "the patient's injury is the scene, not a change: a text figure")]}),
    30: ({"healer": HEALER}, "Healing", "Healers ask whether water, food storage and living conditions cause recurring illness.",
         {0: [c.text_only("food", "food storage is studied, not gained or lost")]}),
    31: ({"veteran": V}, None, "A veteran teaches a ceremonial defensive dance with wooden practice shields.", {}),
    32: ({"fighter1": V, "fighter2": V}, None, "Two practitioners meet in a supervised contest of balance, agility and restraint.", {}),
    33: ({"defender": V}, None, "A young defender asks whether bravery means fighting or protecting others.", {}),
    34: ({"historian": V}, "Research", "Two preserved records tell the founding of a village in contradictory ways.", {}),
    35: ({"elder": c.ELDER}, None, "An elder tells a story that challenges the official account of an old disaster.", {}),
    36: ({"builder": V}, None, "Builders uncover a sealed cache of barkcloth records and carved tablets.", {}),
    37: ({"explorer": V}, None, "Explorers find plans for a woven vessel meant to fly above the sea under a heated envelope.", {}),
    38: ({"inventor": V}, None, "An inventor proposes a sealed wooden-and-metal vessel that could travel beneath the waves.", {}),
    39: ({"boatbuilder": V}, None, "A boatbuilder dreams of an enormous canoe with many hull supports and intricate sails.", {}),
    40: ({"traveler": V}, None, "A traveler describes a craft hanging beneath a great canopy that catches the winds of the sky.", {}),
    41: ({"explorer": V}, None, "An expedition finds a sheltered cove behind towering cliffs.", {}),
    42: ({"explorer": V}, None, "A mysterious craft drifts offshore, moved by a mechanism hidden beneath its hull.", {}),
    43: ({"weaver": V}, None, "A master weaver uses mathematical patterns to make a cloth stronger than expected.", {}),
    44: ({"naturalist": V}, "Research", "A naturalist claims to recognise distinct calls used by a colony of seabirds.", {}),
    45: ({"mapmaker": V}, "Research", "A mapmaker combines explorers' accounts into a new map of the island.", {}),
    46: ({"mechanist": V}, "Building", "A craftsperson builds moving figures powered by flowing water and falling weights.", {}),
    47: ({"historian": V, "artisan": V}, "Research", "A historian and an artisan debate how to restore a fragile ancestral object.", {}),
    48: ({"villager": V}, None, "Masters of every village discipline gather to exchange methods and discoveries.", {}),
}
TAGS = {1: "SUCCESS:", 2: "SETBACK:", 3: "SURPRISE:"}
# "The village holds a nighttime festival to celebrate celestial cycles." (024, L602): the whole village celebrates.
CELEBRATE = {(24, 3): [c.celebrate_all()]}


def build(row: dict) -> dict:
    num = c.num_of(row)
    roles, reward, desc, notes = E[num]
    assert c.description_ok(desc), (num, desc)
    h = c.heading_line(row, HEAD)
    title = c.re.split(HEAD, c.line(h), maxsplit=1)[1].strip()
    spec, setup, choices_at, outs, hook = h + 2, h + 4, h + 6, (h + 11, h + 13, h + 15), h + 17
    assert c.line(spec).startswith("Primary specialty:") and c.line(setup).startswith("SETUP:"), row["id"]
    assert c.line(choices_at) == "CHOICES:" and c.line(hook).startswith("FOLLOW-UP HOOK:"), row["id"]
    ledger = c.group_heading_ledger(row, h)
    ledger += [{"src": c.L(spec), "kind": "note", "why": "the specialty heading: who the event is about (the roles)"},
               {"src": c.L(choices_at), "kind": "structural", "why": "the choices' heading"}]
    cuts: dict[int, list[str]] = {}
    for k, n in enumerate(outs, 1):
        ledger.append({"src": c.L(n), "kind": "note", "text": TAGS[k],
                       "why": "designer tag on the outcome seed (L83: seeds, not results tied to choices)"})
        cuts[n] = [TAGS[k]]
    ledger.append({"src": c.L(hook), "kind": "note", "why": "FOLLOW-UP HOOK: a designer note, never shown"})
    first = next(iter(roles))
    nodes = {
        "setup": {"type": "question", "name": "The setup", "text": c.shown(setup), "src": c.L(setup),
                  "choices": [{"label": c.shown(n), "next": "outcome", "src": c.L(n)}
                              for n in (choices_at + 1, choices_at + 2, choices_at + 3)]},
        "outcome": {"type": "branch", "children": [{"next": f"o{k}"} for k in (1, 2, 3)]},
    }
    if notes.get(0):
        nodes["setup"]["text_only"] = c.with_src(notes[0], c.L(setup))
    for k, n in enumerate(outs, 1):
        eff = [c.skill(first, reward)] if (k == 1 and reward) else []
        eff += CELEBRATE.get((num, k), [])
        nodes[f"o{k}"] = c.page(f"Outcome {k}", c.shown(n, cuts), c.L(n), eff, notes.get(k, ()))
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if not (r == first and reward)]   # cast for the gate only: no effect, no token
    if cast_only:
        col["cast_only"] = cast_only
    return {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": c.ALL, "collection": col,
            "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "setup", "nodes": nodes}


def main() -> int:
    rows = c.rows("c5a")
    assert len(rows) == len(E) == 48
    return c.write_and_check([(r["section"], r["id"], build(r)) for r in rows])


if __name__ == "__main__":
    sys.exit(main())
