"""Chunk K9: write the Companion Anthology's The Inner Lives of Isola (Stone, Spirit, Strangers & Mind and Belonging,
Volume II, events 068-097, companion L6775-7073) as data/event_collection/companion/sss/, and The Living Catalogue's
events 117-154 (companion L8501-8955) as data/event_collection/companion/cat/, then format and check them.

THE INNER LIVES OF ISOLA (068-097) has the format of Stone, Spirit 001-067 (gen_k8.py, whose build() it reuses):
  EVENT NNN: Title / Premise: / A. label / Outcome: / B. / Outcome: / C. / Outcome: / Context and callbacks: (a note)
Its tribal narration rules (L6773: no diagnoses, no cure narrative, "not every difference is an illness") and the
retroactive note (L7075-7078) are notes rows.  The volume treats emotional life and difference as ordinary village
life, so its outcomes stay flavor-only apart from the hands-on and caregiving gains below; nothing in it is a harm.

THE LIVING CATALOGUE (117-154):
  EVENT NNN — Title / Premise: / four pairs of CHOICE: label / OUTCOME: text / Context / follow-up: (a note)
- A true 1:1 choice: the premise is the question page with the four labels, each leading to its own answer page.
  "Premise:", "CHOICE:" and "OUTCOME:" are structural markers; "Context / follow-up:" is a designer note.
- The implementation prompt (L8957-8961: a searchable species catalogue) is a notes row: no game mechanism holds it.
- 117-123 (cat_magic_fish), 124-129 (cat_magic_plants), 130-134 (cat_creatures) are template series: the species
  names are literal text, one file per event.
- Grammar (grammar-fixes.md, companion rows): "a Oriental" L8538, "a Orange" L8550, "a Aureus" L8622 take "an";
  "the The Golden Guppy" L8574 loses the doubled article.

CASTING (the lead's decisions, 2026-11-14): elders 55+; a child 3-13; a teen 14-17 (086's "young apprentice" at a
worksite is a teen); an adult 18+; anyone else 14+.  Trades the text names as a qualification are skilled roles (a
gardener, a healer, a researcher or scientist).  Keepers, visitors, magicians, perfumers, botanists and the aquarium
are text figures where no effect lands on them.  A magician who acts (117-123 choice C; 150's claim) makes the event
VV3-VV5 only (collection_manifest.COMPANION_GAMES).  Kin beyond the coming roles (095's grandchild) is text (gap C2);
a dead child or sibling in a premise (085, 095) stays generic text (gap C3).

EFFECTS (V28 consequence rules; hands-on work earns a small skill, caregiving a small Parenting):
- Inner Lives: 069 B the helper's Farming (shares the garden work), C the healer's Healing (checks sleep, food, pain);
  075 A the healer's Healing (helps the elder rest); 077 B the healer's Healing (considers illness, arranges
  follow-up); 088 B the apprentice's Healing (taught by the healer); 093 the adult's Parenting on every answer (the
  child's fears heard, planned for, prepared).
- Catalogue: 117-123 B the keeper's Research (controls feeding and water changes), C the apprentice's Research
  (records what can be measured); 124-129 A the gardener's Farming (a propagated cutting), B the gardener's Research
  (logs a season); 130-134 A the apprentice's Research (sketches behavior and habitat); 135 C the dye maker's Research
  (a mineral glaze); 138 A the fisher's Research (the survey); 139 B the scientist's Research (tracks weather);
  140 A the child's Research (records surfacing patterns); 144 A and C the jeweler's Research (habitat, husbandry);
  145 A the scholar's Research; 148 B the botanist's Farming (grows comparison specimens); 149 D the perfumer's
  Research (a new blend); 150 A the craftsperson's Research (finds a physical reason); 151 D the child's Research
  (studies the anatomy); 152 A the healer's Healing (provides treatment); 153 B the diver's Research (the sample
  examined); 154 A the apprentice's Research (trained by the elder).
- Harm: 152 C "The attempt may fail medically": the outcome's own alternatives, split by weight -- no change (20), the
  critically ill villager worsens (rare, 5: health_change -60..-40), or dies (very rare, 2: kill, Unknown causes).
  The patient keeps protected "auto" (no allow).
- Words the effects table reads that change nothing get text_only with the reason.

    python scripts/companion/gen_k9.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import companion_common as c  # noqa: E402
import gen_k8 as k8  # noqa: E402

cc, lib = c.cc, c.lib
V, G, CH, EL, TEEN = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.TEEN
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")
GARDENER = c.skilled(V, "Farming")
MAGIC = [3, 4, 5]
T = c.text_only


def sk(role: str, skill: str) -> dict:
    return c.skill(role, skill)


# ---- The Inner Lives of Isola, 068-097 (gen_k8.build's table shape) -------------------------------------------------
SSS = {
    68: ({"villager": V}, "A villager who looked forward to the festival is distressed by its drums, voices and fires.",
         {"to": {0: [T("the celebration", "the festival already under way; the event adds none")]}}),
    69: ({"gardener": GARDENER, "helper": V, "healer": HEALER},
         "A gardener has lost interest in flowers, meals and familiar games for many days.",
         {"eff": {"b": [sk("helper", "Farming")], "c": [sk("healer", "Healing")]},
          "to": {"c": [T("pain and safety", "the healer checks; nobody is found hurt or ill")]}}),
    70: ({"apprentice": V}, "An apprentice keeps fearing the workshop fire was left burning, even after checking.", {}),
    71: ({"child": CH, "friend": CH},
         "A child who notices tiny insect patterns struggles when friends change a game's rules without warning.", {}),
    72: ({"craftsperson": V}, "A craftsperson starts five beautiful necklaces and struggles to finish one commission.",
         {}),
    73: ({"child": CH}, "During a long lesson, a child who wants to learn fidgets, wanders and misses instructions.", {}),
    74: ({"fisher": V}, "After surviving a frightening storm, a fisher startles at harmless thunder and avoids the shore.",
         {}),
    75: ({"elder": EL, "healer": HEALER, "friend": V},
         "An elder has slept poorly for weeks and grows irritable with friends.",
         {"eff": {"a": [sk("healer", "Healing")]}}),
    76: ({"worker": V, "coworker": V}, "A strong worker has days of deep fatigue that others cannot see.", {}),
    77: ({"villager": V, "healer": HEALER}, "A villager has eaten little since a loss and says nothing tastes good.",
         {"eff": {"b": [sk("healer", "Healing")]}}),
    78: ({"teen": TEEN}, "A teen knows an answer but freezes when asked to speak before the whole village.", {}),
    79: ({"villager": V, "friend": V}, "A villager is upset when an unexpected change disrupts a cherished routine.", {}),
    80: ({"teen": TEEN, "sibling": c.related(V, "sibling_of", "teen")},
         "A normally patient teen bursts into tears after several small frustrations.", {}),
    81: ({"adult": G, "friend": V}, "A familiar smell brings back a frightening childhood memory, leaving an adult shaken.",
         {}),
    82: ({"child": CH, "instructor": V},
         "A child struggles with spoken counting but invents a clever way to group shells.", {}),
    83: ({"villager": V, "friend": V}, "A villager has stopped attending gatherings but still enjoys fishing alone.", {}),
    84: ({"caregiver": G}, "A kind caregiver is distressed by a frightening thought they never wanted.", {}),
    85: ({"parent": G}, "A grieving parent cannot bear to attend the first harvest feast since their child died.",
         {"to": {"c": [T("help prepare food", "a small task at the feast; no food is made or stored")]}}),
    86: ({"apprentice": TEEN, "mentor": V},
         "After witnessing a serious accident, a young apprentice struggles to concentrate during lessons.", {}),
    87: ({"villager": V}, "A villager has an unusually energetic day, starts grand projects and sleeps little.",
         {"to": {0: [T("whether to celebrate", "the friends' question; nobody celebrates")]}}),
    88: ({"healer": HEALER, "apprentice": V}, "A quiet healer dislikes crowded meetings but is attentive with patients.",
         {"eff": {"b": [sk("apprentice", "Healing")]},
          "to": {0: [T("dislikes crowded meetings", "the healer's temperament; meetings are no game preference")]}}),
    89: ({"storyteller": V, "friend": V},
         "A lively storyteller privately admits they feel empty despite making others laugh.", {}),
    90: ({"villager": V}, "A villager wants to visit a distant part of Isola but fears being trapped far from home.", {}),
    91: ({"coworker1": V, "coworker2": V, "elder": EL},
         "Two coworkers hear the same remark differently, and one is overwhelmed by the quick exchange.", {}),
    92: ({"researcher": SCHOLAR}, "A researcher completes a long project but feels no triumph, only exhaustion.", {}),
    93: ({"child": c.sexed(CH, "male"), "adult": G},
         "A child keeps asking whether their family will be safe when the rains come.",
         {"eff": {"a": [c.parenting("adult")], "b": [c.parenting("adult")], "c": [c.parenting("adult")]}}),
    94: ({"trainee": V, "mentor": V}, "A trainee is confused when a mentor gives six directions at once.", {}),
    95: ({"elder": EL}, "An elder cries while repairing a toy that belonged to a sibling who has died.", {}),
    96: ({"potter": V}, "A potter keeps destroying good work because each pot has a tiny flaw.", {}),
    97: ({"teen": TEEN}, "A teen feels different from peers and believes everyone else has found close friends.", {}),
}


# ---- The Living Catalogue, 117-154 ----------------------------------------------------------------------------------
CAT_HEAD = r"^EVENT \d{3}\s+-\s+"          # "EVENT 117 — " after the source's typography is normalised
FIX = {8538: [("a Oriental", "an Oriental")], 8550: [("a Orange", "an Orange")],
       8574: [("the The Golden Guppy", "the Golden Guppy")], 8622: [("a Aureus", "an Aureus")]}

MAGIC_FISH = ({"keeper": V, "apprentice": V}, {"b": [sk("keeper", "Research")], "c": [sk("apprentice", "Research")]})
MAGIC_PLANT = ({"gardener": GARDENER}, {"a": [sk("gardener", "Farming")], "b": [sk("gardener", "Research")]})
CREATURE = ({"apprentice": V, "keeper": V}, {"a": [sk("apprentice", "Research")]})

# num: (roles, description, opts) -- opts: eff {"a".."d": [effects]}, to {0|"a".."d": [text_only]}, split, games
CAT = {
    135: ({"dye_maker": V}, "A rare reef fish sheds scales that make seawater-proof dyes, and only three such fish are known.",
          {"eff": {"c": [sk("dye_maker", "Research")]}}),
    136: ({"elder": EL, "diver": V}, "An elder in pain begs for a pearl from an endangered mollusk said to ease pain.", {}),
    137: ({"villager": V}, "A rare vine's luminous sap could mark trails, but cutting it may kill its only stem.", {}),
    138: ({"fisher": V, "jeweler": V}, "A fisher blames an otter for the dwindling abalone, and a jeweler wants the shells.",
          {"eff": {"a": [sk("fisher", "Research")]}}),
    139: ({"scientist": SCHOLAR}, "A Nox Orchid is said to bloom near the grieving, but a scientist sees it follows rain.",
          {"eff": {"b": [sk("scientist", "Research")]}}),
    140: ({"child": CH, "fisher": V}, "A pod of orcas follows the outer reef: fishers want them chased off, children want to watch.",
          {}),
    141: ({"child": CH, "naturalist": SCHOLAR}, "A cormorant keeps dropping small fish near a jetty, and a hungry child thinks it is sharing.",
          {"to": {0: [T("sharing food", "the child's belief about the bird; no food is gained")],
                  "c": [T("whether food is safe", "a lesson; no food is gained or stored")]}}),
    142: ({"villager": V}, "A pale bird appears on Isola's coolest high ridge, and nobody agrees whether it belongs there.",
          {"to": {"d": [T("the bird disappears", "a bird flies off; no villager disappears")]}}),
    143: ({"child": CH}, "Large striped shapes glimpsed in the foliage convince a child that a tiger lives on Isola.", {}),
    144: ({"jeweler": V}, "A rare beetle's secretion cleans tarnished metal, and a jeweler wants to keep hundreds.",
          {"eff": {"a": [sk("jeweler", "Research")], "c": [sk("jeweler", "Research")]}}),
    145: ({"scholar": SCHOLAR}, "A scholar proposes cataloguing every living thing on Isola, a task that seems impossible.",
          {"eff": {"a": [sk("scholar", "Research")]}}),
    146: ({"artist": V}, "A renowned artist paints a Greenfin Spotanus with the wrong fin and the wrong name.", {}),
    147: ({"keeper": V}, "A keeper finds an aquarium empty after a storm, with no dead fish in sight.", {}),
    148: ({"botanist": GARDENER}, "A more experienced botanist says a Painted Tigerfern was named wrongly.",
          {"eff": {"b": [sk("botanist", "Farming")]}}),
    149: ({"perfumer": V}, "A rare Fourpetal Maple's scent draws night pollinators, and perfumers want its flowers.",
          {"eff": {"d": [sk("perfumer", "Research")]}}),
    150: ({"craftsperson": V}, "A conch horn makes two distinct notes, and a magician claims it answers questions.",
          {"eff": {"a": [sk("craftsperson", "Research")]}, "games": MAGIC}),
    151: ({"child": CH}, "A child records ants carrying flower fragments but draws them with too many legs.",
          {"eff": {"d": [sk("child", "Research")]}}),
    152: ({"patient": V, "healer": HEALER},
          "A critically ill villager might be helped by an endangered reef animal's secretion, but evidence is thin.",
          {"eff": {"a": [sk("healer", "Healing")]},
           "split": {"c": [
               (20, None, [], []),
               (5, "rare", [{"do": "health_change", "role": "patient", "min": -60, "max": -40}], []),
               (2, "very_rare", [{"do": "kill", "role": "patient", "cause": "unknown"}], [])]}}),
    153: ({"diver": V}, "A diver finds a reef covered in tiny organisms whose patterns look like writing.",
          {"eff": {"b": [sk("diver", "Research")]}}),
    154: ({"elder": c.skilled(EL, "Research"), "apprentice": V},
          "An elderly scientist with hundreds of uncertain sketches fears dying before the catalogue is done.",
          {"eff": {"a": [sk("apprentice", "Research")]}}),
}


def an(word: str) -> str:
    return ("an " if word[:1] in "AEIOU" else "a ") + word


def cat_premise_desc(num: int, premise: str) -> str:
    """A template premise in fewer words (117-134)."""
    if 117 <= num <= 123:
        m = re.match(r"A keeper records (.+?) near an? (.+?), a fish associated in island stories with the (?:The )?(.+?)\.",
                     premise)
        return f"A keeper records {m.group(1)} near {an(m.group(2))}, tied in stories to the {m.group(3)}."
    if 124 <= num <= 129:
        m = re.match(r"A gardener tends an? (.+?), remembered in Isolan lore as the (.+?)\.", premise)
        return f"A visitor asks a gardener for a cutting of {an(m.group(1))}, known in Isolan lore as the {m.group(2)}."
    m = re.match(r"An? (.+?) is seen", premise)
    return f"An apprentice wants to add {an(m.group(1))} to the creature catalogue, but its habits are little known."


def cat_plan(num: int, premise: str):
    if 117 <= num <= 123:
        roles, eff = MAGIC_FISH
        to = {}
        if num == 121:
            to = {0: [T("Magic Fish of Health", "the legend's name; nobody's health changes")]}
        to.setdefault(0, []).append(T("water, food, chance", "explanations offered; no food is gained or lost"))
        return roles, cat_premise_desc(num, premise), {"eff": eff, "to": to, "games": MAGIC}
    if 124 <= num <= 129:
        roles, eff = MAGIC_PLANT
        return roles, cat_premise_desc(num, premise), {"eff": eff}
    if 130 <= num <= 134:
        roles, eff = CREATURE
        return roles, cat_premise_desc(num, premise), {"eff": eff}
    return CAT[num]


def shown(n: int) -> str:
    with lib.use_source(lib.COMPANION_ID):
        p = cc.processed_line(n, {}, FIX)
    return p[:1].upper() + p[1:]


def build_cat(row: dict) -> dict:
    num = c.num_of(row)
    h = c.heading_line(row, CAT_HEAD)
    premise, note = h + 1, h + 10
    assert c.line(premise).startswith("Premise:"), row["id"]
    assert c.line(note).startswith("Context / follow-up:") and note == row["lines"][1], row["id"]
    roles, desc, opts = cat_plan(num, shown(premise))
    assert c.description_ok(desc), (row["id"], desc, len(desc))
    title = re.split(CAT_HEAD, c.line(h), maxsplit=1)[1].strip()
    ledger = c.group_heading_ledger(row, h)
    ledger.append({"src": c.L(note), "kind": "note",
                   "why": "Context / follow-up: the designer's catalogue and cross-reference notes, never shown"})
    eff, tonly, split = opts.get("eff", {}), opts.get("to", {}), opts.get("split", {})
    choices, nodes = [], {}
    for i, k in enumerate("abcd"):
        lab, out = h + 2 + 2 * i, h + 3 + 2 * i
        assert c.line(lab).strip().startswith("CHOICE:") and c.line(out).strip().startswith("OUTCOME:"), (row["id"], k)
        choices.append({"label": shown(lab), "next": k, "src": c.L(lab)})
        name = f"Answer {k.upper()}"
        if k in split:
            kids = []
            for j, (w, rar, fx, to) in enumerate(split[k], 1):
                kid = {"next": f"{k}{j}", "weight": w}
                if rar:
                    kid["rarity"] = rar
                kids.append(kid)
                nodes[f"{k}{j}"] = c.page(f"{name} ({j})", shown(out), c.L(out), fx, to)
            nodes[k] = {"type": "branch", "name": name, "children": kids}
        else:
            nodes[k] = c.page(name, shown(out), c.L(out), eff.get(k, ()), tonly.get(k, ()))
    q = {"type": "question", "name": "The premise", "text": shown(premise), "src": c.L(premise), "choices": choices}
    if tonly.get(0):
        q["text_only"] = c.with_src(tonly[0], c.L(premise))
    nodes = {"premise": q, **nodes}
    col = {"id": row["id"], "title_src": c.L(h), "ledger": ledger, "description": desc}
    cast_only = [r for r in roles if r not in k8.used_roles(nodes)]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": opts.get("games", c.ALL),
           "collection": col, "requirement": {"min_eligible": len(roles)}, "roles": roles, "start": "premise",
           "nodes": nodes}
    fixes = [{"src": c.L(n), "before": b, "after": a} for n in range(row["lines"][0], row["lines"][1] + 1)
             for b, a in FIX.get(n, [])]
    if fixes:
        doc["grammar_fixes"] = fixes
    return doc


def main() -> int:
    k8.D = SSS
    sss = [r for r in c.rows("sss") if c.num_of(r) in SSS]
    cat = [r for r in c.rows("cat") if c.num_of(r) >= 117]
    assert len(sss) == 30 and len(cat) == 38, (len(sss), len(cat))
    docs = [(r["section"], r["id"], k8.build(r)) for r in sss] + [(r["section"], r["id"], build_cat(r)) for r in cat]
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
