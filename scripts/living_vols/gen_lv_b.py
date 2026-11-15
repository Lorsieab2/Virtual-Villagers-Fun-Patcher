"""Chunk LV-B: write the Living Event Engine's next four fixed event volumes as collection events, then format and
check them:
  PEOPLES-01..37  Colors, Masks, Peoples and Choice                       living L21665-22160 (lv_peoples)
  UNSEEN-01..39   The Unseen Horizon, Cryptids, and the Silent Gods       living L22180-22685 (lv_unseen)
  WAYS-01..38     The Many Ways of Isola (four choices)                   living L22704-23310 (lv_ways)
  AUTH-01..30     The Weight of a Name (four choices)                     living L23331-23809 (lv_auth)
The shape, the weights and the helpers are scripts/living_vols/living_common.py's (as LV-A, gen_lv_a.py).

THE TABLE BELOW IS THE AUTHORING RECORD (the owner's rules, the lead's briefs of 2026-11-14/15):
- Text verbatim, no sensitivity edit: UNSEEN-37's "a pleasant afterlife" stays as written (the owner, 2026-11-15).
  Nothing else names a word the owner listed for change;
  the volumes' "gods", "spirits", Biggles (the games' own creature) and the hinted beings (an ancient guardian, the
  sky stag, a long-necked shape) stay as written, every mystery unresolved.
- VV5 ONLY (the source's tag on the setup or heading): games [5].  Heathens and masks stay vanilla VV5 words; with
  Guardians of Isola Rewrite every Heathen word becomes Isolan (the source's GUARDIANS OF ISOLA VARIANT line and
  guardians-wording.md; a label gets a sibling choice shown only with the patch).  AUTH-17 (a masked adviser) is
  vanilla only (the volume's note: "VV5 masked/heathen material is vanilla-only"); AUTH-18 is the Guardians of Isola
  form only (its heading).
- The Chief rule: outside VV3 the text's "chief" is the game word {@chief} ("chief" in VV3, "leader" elsewhere);
  a title with "Chief" has a "Leader" title variant in VV1, VV2, VV4 and VV5 (as K6's "The Unpopular Leader").
- Magic is VV3-VV5 lore (the lead, as LV-A's MED-19): a choice that asks a Magic adept, master, spell or charm shows
  only in VV3-VV5 (the event keeps every game, with three choices left); WAYS-13 and WAYS-35, whose setup is magic,
  are VV3-VV5 events.
- The text names nobody and uses "their": roles carry no token.  A role casts the person an effect lands on, or the
  person the scene needs (collection.cast_only).  Ages: a child 3-13, a young villager 14-25, an elder 55+.
- Effects only where an outcome's own words support one (as LV-A): a death is kill (cause "unknown"), very rare; a
  villager who goes missing for good ("never returns", "goes missing", "fails to return") is vanish, rare, the
  search told in the text (the volume: a missing villager is not automatically dead); "becomes ill", "fall ill" is
  sick; a worsening, a reaction, an irritation, an injury or exhaustion of a cast villager is a minor setback
  (health -30..-10); "improves", "recover" is a small health gain; a skilled villager who finds, identifies,
  discovers or learns a result gains a small skill; food the village spends, loses or gains is a small food loss or
  gain; "celebrates" is celebrate.  Hair dye the villager keeps is the random new head look (appearance head
  "random", the owner 2026-11-15: PEOPLES-01 A1 and C1, PEOPLES-04 A1, PEOPLES-31 A2); clothing dye stays text only
  (rule 8: no chosen-colour action).  Feelings, councils, customs, relationships,
  reputations, trust and lasting states are text only (rules 7-9).
- Protection: every harm-capable role keeps protected "auto".  The harm list is in
  docs/event-collection/retrofit-harm-review.md.

    python scripts/living_vols/gen_lv_b.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import living_common as c  # noqa: E402

V, G, CH, EL, YG, YS = c.VILLAGER, c.GROWN, c.CHILD, c.ELDER, c.YOUNG, c.YOUNGSTER
HEALER = c.skilled(V, "Healing")
SCHOLAR = c.skilled(V, "Research")
FARMER = c.skilled(V, "Farming")
BUILDER = c.skilled(V, "Building")
sk, minor, better, ill, die, food, T = c.sk, c.minor, c.better, c.ill, c.die, c.food, c.T
LOSS = c.food("small", loss=True)
GAIN = c.food("small")
PREMISE = "the premise: it happened before the event; nobody is harmed now"
MAGIC = {"game": [3, 4, 5]}          # a Magic choice: magic is VV3-VV5 lore
DYE = "rule 8: the games have no chosen-colour action (clothing); hair dye is the random new head look (the owner)"
G_IF = c.GUARDIANS_IF
# The Guardians of Isola Rewrite pairs, in the order they are made (guardians-wording.md): the article first.
HEATHEN_PAIRS = [("A Heathen", "An Isolan"), ("a Heathen", "an Isolan"), ("Heathens", "Isolans"),
                 ("Heathen", "Isolan")]


def any_skill(role: str) -> dict:
    """ "learns a different skill": a small gain in one of the skills every game has, at random."""
    return dict(sk(role, "Building"), skills=["Building", "Farming", "Healing", "Research"])


def hair(role: str) -> dict:
    """Hair dye the villager keeps: the random new head look ("hair changes color"; the owner, 2026-11-15)."""
    return {"do": "appearance", "role": role, "head": "random"}


def vanish(role: str) -> dict:
    return {"do": "vanish", "role": role}


def cheer(role: str | None = None) -> dict:
    return {"do": "celebrate", "who": role or "all"}


# PREFIX-NN: ({role: spec}, description or None (the setup), opts)
PEOPLES = {
    1: ({"villager": V}, None,
        {"fx": {"a1": [hair("villager")], "c1": [hair("villager")], "c2": [minor("villager")]}}),
    2: ({"villager": V, "dyer": V}, None, {"to": {"a1": [T("the blue clothing", DYE)]}}),
    3: ({"tailor": V, "wearer": V}, None,
        {"fx": {"c1": [cheer("wearer")]},
         "to": {"a2": [T("an elder dislikes the change", "an elder's opinion, not a game preference")]}}),
    4: ({"elder": EL}, None, {"fx": {"a1": [hair("elder")]}}),
    5: ({"weaver": V}, None, {}),
    6: ({"villager": V}, None, {}),
    7: ({"villager": V}, None, {}),
    8: ({"villager": V}, None, {}),
    9: ({"villager": V}, None, {}),
    10: ({"child": CH}, "Children from different communities both claim a beautiful shell.", {}),
    11: ({"villager": V}, None,
         {"to": {0: [T("an injured villager", PREMISE)],
                 "a2": [T("the helper dislikes", "the helper is not a cast villager: no preference changes")]}}),
    12: ({"villager": V}, None, {}),
    13: ({"villager": V}, None, {}),
    14: ({"villager": G}, None, {}),
    15: ({"villager": V}, None, {}),
    16: ({"villager": V}, None,
         {"to": {"b1": [T("the offer of food", "what the visitors understand; nothing is gained or lost")]}}),
    17: ({"villager": V}, None, {}),
    18: ({"villager": V}, None,
         {"to": {"a1": [T("provides food", "the agreement's purpose over the seasons; nothing is gained now")]}}),
    19: ({"apprentice": V}, None, {}),
    20: ({"weaver": V}, None, {}),
    21: ({"villager": V}, None, {}),
    22: ({"child": c.sexed(CH, "female")}, None, {}),
    23: ({"villager": V}, None, {}),
    24: ({"villager": V}, None,
         {"fx": {"c1": [LOSS], "c2": [LOSS]}}),
    25: ({"villager": V}, None, {}),
    26: ({"villager": V}, None,
         {"fx": {"a1": [GAIN], "a2": [GAIN], "b1": [GAIN], "b2": [GAIN]},
          "to": {0: [T("sends food", "the gift is given only if the village accepts it")]}}),
    27: ({"villager": V}, None, {}),
    28: ({"musician": V}, None, {}),
    29: ({"child": CH}, None,
         {"to": {"a1": [T("everyone needs food", "the child's thought; nothing is gained or lost")]}}),
    30: ({"tailor": V}, None, {}),
    31: ({"villager": V}, None,
         {"fx": {"a2": [hair("villager")]},
          "to": {0: [T("dyes their hair and clothing", "the premise: the dye is already on; nothing changes now")],
                 "a1": [T("a familiar shade", "the games cannot give back a villager's earlier look")]}}),
    32: ({"villager": V}, None, {}),
    33: ({"villager": V}, None,
         {"to": {"a1": [T("the celebration", "the festival already under way: no new celebration starts")]}}),
    34: ({"villager": V}, None, {}),
    35: ({"villager": V}, None, {}),
    36: ({"villager": V}, None, {}),
    37: ({"villager": V}, None,
         {"to": {"a1": [T("trade food", "an exchange: nothing is gained or lost overall")]}}),
}

UNSEEN = {
    1: ({"scholar": SCHOLAR}, None, {}),
    2: ({"fisher": V}, None, {"to": {0: [T("disappears", "the sail, not a villager")]}}),
    3: ({"explorer": YG}, None, {}),
    4: ({"cartographer": SCHOLAR, "novice": V}, None, {}),
    5: ({"elder": EL, "child": CH}, None, {}),
    6: ({"villager": V}, None, {"to": {"c1": [T("disappears", "the chest, not a villager")]}}),
    7: ({"villager": YG}, None, {}),
    8: ({"musician": V, "researcher": SCHOLAR}, None, {}),
    9: ({"hunter": V}, None,
        {"to": {"a2": [T("vanishes overnight", "the hunter returns: nobody is lost")]}}),
    10: ({"explorer": V, "elder": EL}, None, {"fx": {"b2": [vanish("explorer")]}}),
    11: ({"scientist": SCHOLAR}, None, {"fx": {"a1": [sk("scientist", "Research")]}}),
    12: ({"naturalist": SCHOLAR}, None,
         {"fx": {"a1": [sk("naturalist", "Research")]},
          "to": {"b1": [T("disappears", "a distant silhouette, not a villager")]}}),
    13: ({"fisher": V}, None, {}),
    14: ({"villager": V, "elder": EL}, None,
         {"to": {"b2": [T("disappears for a day", "the villager comes back: nobody is lost")]}}),
    15: ({"craftsperson": V}, None, {"to": {"b1": [T("vanish", "the flowers, not a villager")]}}),
    16: ({"scientist": c.skilled(YG, "Research")}, None,
         {"fx": {"b1": [sk("scientist", "Research")], "c2": [vanish("scientist")]}}),
    17: ({"child": CH}, None, {}),
    18: ({"sailor": V, "naturalist": SCHOLAR}, None, {}),
    19: ({"villager": V}, None, {}),
    20: ({"elder": EL}, None, {}),
    21: ({"elder": EL}, None, {}),
    22: ({"child": CH, "healer": HEALER}, None, {"fx": {"b1": [cheer("child")]}}),
    23: ({"believer": V, "scientist": SCHOLAR}, None, {}),
    24: ({"patient": V, "scholar": SCHOLAR}, None,
         {"fx": {"a2": [minor("patient")], "c1": [sk("scholar", "Research")]},
          "to": {0: [T("a sick villager", PREMISE)]}}),
    25: ({"child": CH}, None,
         {"to": {"c1": [T("experience", "the family's experience of the night: no skill is meant")]}}),
    26: ({"villager": V}, None, {}),
    27: ({"villager": V}, None, {"to": {0: [T("a deceased grandmother", "a death long past: the premise")]}}),
    28: ({"child": CH}, None, {}),
    29: ({"elder": EL, "scientist": SCHOLAR}, None, {"fx": {"b1": [sk("scientist", "Research")]}}),
    30: ({"villager": V, "apprentice": V}, None, {"fx": {"b1": [cheer()]}}),
    31: ({"scientist": SCHOLAR}, None, {"fx": {"c1": [sk("scientist", "Research")]}}),
    32: ({"explorer": V}, None, {"fx": {"b2": [vanish("explorer")]}}),
    33: ({"villager": V}, None, {}),
    34: ({"researcher": SCHOLAR}, None, {}),
    35: ({"elder": EL}, None, {"to": {0: [T("near death", "the elder's age and illness: no outcome says they die")]}}),
    36: ({"relative": V}, None, {}),
    37: ({"storyteller": V}, None, {}),       # "a pleasant afterlife" kept as written (the owner, 2026-11-15)
    38: ({"villager": V}, None, {}),
    39: ({"smith": V, "child": CH}, None, {}),
}

WAYS = {
    1: ({"adept": V}, None,
        {"fx": {"a1": [minor("adept")]}, "cif": {"a": MAGIC},
         "to": {"a1": [T("collapses", "the adept collapses from exhaustion, not a structure")]}}),
    2: ({"villager": V}, None, {"cif": {"b": MAGIC}}),
    3: ({"carpenter": BUILDER}, None, {"cif": {"c": MAGIC}}),
    4: ({"apprentice": FARMER}, None, {"fx": {"b1": [sk("apprentice", "Farming")]}, "cif": {"c": MAGIC}}),
    5: ({"fisher": V}, None, {"fx": {"b1": [GAIN]}}),
    6: ({"elder": EL}, None, {"fx": {"b2": [LOSS], "c2": [LOSS], "d1": [LOSS]}, "cif": {"d": MAGIC}}),
    7: ({"inventor": BUILDER}, None, {"cif": {"c": MAGIC}}),
    8: ({"elder": EL, "youngster": YG}, None, {}),
    9: ({"elder": EL, "apprentice": V, "villager": V}, None, {"fx": {"d2": [ill("villager")]}}),
    10: ({"daughter": c.sexed(V, "female")}, None, {}),
    11: ({"son": c.sexed(YG, "male")}, None, {}),
    12: ({"parent": G, "healer": HEALER}, None,
         {"to": {"a2": [T("the death", "the child's death is the premise; nobody dies now")]}}),
    13: ({"master": V, "scientist": SCHOLAR}, None,
         {"fx": {"a2": [minor("master")], "b1": [sk("scientist", "Research")]},
          "to": {0: [T("a celebrated feat", "a feat of the past: no celebration now")]}}),
    14: ({"villager": V}, None,
         {"cif": {"d": MAGIC}, "to": {"a2": [T("no injury", "nobody is hurt: the animal is examined")]}}),
    15: ({"botanist": SCHOLAR}, None,
         {"fx": {"a1": [GAIN], "c1": [sk("botanist", "Farming")]},
          "to": {"b2": [T("a possible new food source", "a chance not taken: no stores are lost")]}}),
    16: ({"mourner": V}, None, {}),
    17: ({"builder": c.skilled(YG, "Building")}, None, {}),
    18: ({"villager": V}, None, {"cif": {"d": MAGIC}}),
    19: ({"patient": V}, None, {"fx": {"a2": [minor("patient")]}, "cif": {"b": MAGIC}}),
    20: ({"villager": V}, None,
         {"fx": {"a1": [LOSS], "c1": [cheer()], "d1": [GAIN], "d2": [LOSS]},
          "to": {0: [T("little food", "the premise: the stores are already low; nothing is lost now")],
                 "b1": [T("food lasts", "the stores last: nothing more is gained or lost")]}}),
    21: ({"explorer": V}, None, {}),
    22: ({"child": CH}, None, {}),
    23: ({"villager": V}, None, {}),
    24: ({"villager": V}, None, {"cif": {"c": MAGIC}}),
    25: ({"villager": V}, None, {}),
    26: ({"elder": EL}, None, {}),
    27: ({"villager": YG}, None,
         {"fx": {"a1": [any_skill("villager")], "b2": [minor("villager")]}}),
    28: ({"tailor": V}, None, {}),
    29: ({"naturalist": SCHOLAR, "child": CH}, None, {}),
    30: ({"villager": V}, None, {"cif": {"c": MAGIC}}),
    31: ({"apprentice": HEALER, "patient": V}, None,
         {"fx": {"a1": [better("patient"), sk("apprentice", "Healing")], "b2": [minor("patient")]}}),
    32: ({"mourner": V}, None, {}),
    33: ({"villager": V}, None, {"cif": {"c": MAGIC}}),
    34: ({"farmer": FARMER}, None, {}),
    35: ({"healer": HEALER, "patient": V}, None,
         {"fx": {"a1": [better("patient"), minor("healer")], "b2": [minor("patient")]},
          "to": {0: [T("a gravely ill patient", PREMISE)]}}),
    36: ({"scientist": c.skilled(YG, "Research"), "elder": EL}, None, {}),
    37: ({"villager": V}, None, {}),
    38: ({"elder": EL}, None, {"to": {0: [T("after their death", "the dying elder's wish: no outcome says they die")]}}),
}

AUTH = {
    1: ({"healer": HEALER, "apprentice": V}, None, {}),
    2: ({"apprentice": c.skilled(YG, "Building"), "master": BUILDER}, None,
        {"fx": {"a1": [sk("apprentice", "Building")], "b1": [sk("apprentice", "Building")]}}),
    3: ({"master": V, "rookie": YG}, None, {"fx": {"a1": [cheer(), GAIN]}}),
    4: ({"elder": EL, "scientist": c.skilled(YG, "Research")}, None,
        {"fx": {"c1": [sk("scientist", "Research")]}}),
    5: ({"worker": V}, None,
        {"to": {"a2": [T("their skills", "the villagers' skills are already theirs: none changes")]}}),
    6: ({"patient": V, "healer": HEALER, "novice": V}, None,
        {"fx": {"a1": [better("patient")], "a2": [minor("patient")], "d1": [better("patient")]},
         "to": {0: [T("an injured villager", PREMISE)],
                "d1": [T("combined skills", "the healers' skills working together: no skill changes")]}}),
    7: ({"storekeeper": V}, None,
        {"to": {0: [T("the village's food stores", "the premise: the damage is already done; nothing is lost now")]}}),
    8: ({"weaver": YG, "elder": EL}, None, {}),
    9: ({"villager": V}, None,
        {"to": {0: [T("collapse", "a riverbank, not a structure")],
                "a2": [T("collapses", "the riverbank and the gardens: no structure of the games")]}}),
    10: ({"candidate": G}, None,
         {"to": {"c1": [T("each other's skills", "the leaders' skills: none changes")]}}),
    11: ({"reader": V}, None, {}),
    12: ({"farmer": FARMER}, None, {}),
    13: ({"keeper": V, "apprentice": V}, None,
         {"to": {"b1": [T("an injury", "the animal's injury, not a villager's")]}}),
    14: ({"cartographer": c.skilled(YG, "Research")}, None, {}),
    15: ({"scientist": SCHOLAR, "apprentice": V}, None, {"fx": {"b1": [sk("apprentice", "Research")]}}),
    16: ({"child": CH, "novice": V}, None, {}),
    17: ({"builder": BUILDER}, None, {}),
    18: ({"worker": V}, None, {}),
    19: ({"scout": YG}, None, {}),
    20: ({"elder": EL}, None,
         {"fx": {"a1": [die("elder")]},
          "to": {0: [T("near death", "the elder's state: only the promise's peaceful ending says they die")]}}),
    21: ({"craftsperson": V}, None, {"fx": {"a2": [ill("craftsperson")]}}),
    22: ({"scientist": SCHOLAR}, None,
         {"fx": {"c1": [sk("scientist", "Research")]}}),
    23: ({"child": CH, "rookie": YG}, None,
         {"to": {"b2": [T("without injury", "nobody is hurt")]}}),
    24: ({"villager": V}, None,
         {"fx": {"b2": [LOSS]},
          "to": {"a1": [T("a food reserve", "the reserve is kept: nothing is gained or lost")]}}),
    25: ({"novice": V}, None, {}),
    26: ({"deputy": G}, None, {}),
    27: ({"villager": V}, None,
         {"to": {"b2": [T("the needed skill", "the worker's skill is as it was: none changes")]}}),
    28: ({"fisher": V}, None,
         {"to": {"a2": [T("food source", "the reef's food over time; nothing is lost now")],
                 "c1": [T("food", "the rules' balance over the seasons; nothing is gained or lost now")]}}),
    29: ({"novice": V, "wearer": V}, None, {"fx": {"a2": [ill("wearer")]}}),
    30: ({"villager": V}, None, {}),
}

# Per-event extras that are not effects
EXTRA = {
    ("lv_auth", 17): {"req_if": {"not": G_IF}},     # vanilla VV5 only: the masked adviser (the volume's note)
    ("lv_auth", 18): {"req_if": G_IF},              # the heading's "GUARDIANS OF ISOLA VV5 ONLY"
}

VOLUMES = (("lv_peoples", PEOPLES, 37), ("lv_unseen", UNSEEN, 39), ("lv_ways", WAYS, 38), ("lv_auth", AUTH, 30))

GUARDIANS_START = "<!-- LV-B Guardians rows: written by scripts/living_vols/gen_lv_b.py -->"
GUARDIANS_END = "<!-- end of the LV-B Guardians rows -->"


def _texts(row: dict) -> list[str]:
    h, last = row["lines"]
    return [row["title"]] + [c.shown(n) for n in range(h + 1, last)]


def guardians_pairs(row: dict) -> list[tuple[str, str]]:
    """The event's Heathen pairs, in order, that its texts use (every pair must be used: check j)."""
    if row["games"] != [5]:
        return []
    left = "\n".join(_texts(row)[:1] + [t for t in _texts(row)[1:] if not t.startswith("GUARDIANS OF ISOLA")])
    out = []
    for before, after in HEATHEN_PAIRS:
        if before in left:
            out.append((before, after))
            left = left.replace(before, after)
    return out


def write_guardians_doc(rows_pairs: list[tuple[dict, list]]) -> None:
    p = c.ROOT / "docs" / "event-collection" / "guardians-wording.md"
    s = p.read_text(encoding="utf-8")
    body = [GUARDIANS_START, "",
            "## The Living Event Engine's Colors, Masks, Peoples and Choice (LV-B)", "",
            "Its VV5 ONLY events say \"Heathen\". The source's own rule for each (\"GUARDIANS OF ISOLA VARIANT:",
            "Replace Heathens with the other Isolan tribe\") is made with the pairs below, in this order, in every text",
            "the event shows: the title, the pages, a label (PEOPLES-08's \"Invite an Isolan to visit instead.\", a",
            "choice shown only with the patch) and the Pick Island Event sentence. No event says \"convert\". The",
            "masks stay (narrative only); AUTH-17 The Masked Adviser is vanilla New Believers only, and AUTH-18 The",
            "Guardians' Council shows only with the patch.", "",
            "| Event | Where | Before | After |", "|---|---|---|---|"]
    for row, pairs in rows_pairs:
        for before, after in pairs:
            body.append(f"| `{row['id']}` | its texts | {before} | {after} |")
    body += ["", GUARDIANS_END]
    block = "\n".join(body)
    if GUARDIANS_START in s:
        a, b = s.index(GUARDIANS_START), s.index(GUARDIANS_END) + len(GUARDIANS_END)
        s = s[:a] + block + s[b:]
    else:
        mark = "## More Island Events (New Believers)"
        s = s.replace(mark, block + "\n\n" + mark)
    p.write_text(s, encoding="utf-8", newline="\n")


def main() -> int:
    docs, guards = [], []
    for section, table, count in VOLUMES:
        rows = c.rows(section)
        assert len(rows) == len(table) == count, (section, len(rows), len(table))
        for r in rows:
            n = c.num_of(r)
            roles, desc, opts = table[n]
            opts = dict(opts, **EXTRA.get((section, n), {}))
            pairs = guardians_pairs(r)
            if pairs:
                opts["guard"] = pairs
                guards.append((r, pairs))
            if section == "lv_auth" and any(re.search(r"\bchief\b", t) for t in _texts(r)[1:]):
                opts["chief"] = True
            if "Chief" in r["title"] and r["games"] != [3]:
                opts["title_v"] = [{"if": {"game": [g for g in r["games"] if g != 3]},
                                    "title": r["title"].replace("Chief", "Leader")}]
            docs.append((section, r["id"], c.build(r, roles, desc, opts)))
    write_guardians_doc(guards)
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
