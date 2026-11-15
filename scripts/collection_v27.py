"""Write the 57 V27 events of the owner's V28 source (data/event_collection/v27/<id>.json), then format and check them.

Each V27 event is eight lines (scripts/collection_manifest.py V27_EVENTS): the heading, AGE/CAST, SETUP, OUTCOME A-C
and FOLLOW-UP.  Every event here is one page: the SETUP, and one OUTCOME appended to it (no choices: the source gives
none, and its global rules say "no-choice events are valid").

THE TABLE BELOW IS THE AUTHORING RECORD.  How it reads the source (lead's brief, 2026-11-14, and the V27 global rules
at L10440-10485):
- Ages: BABIES = the nursing state (VV babies are not villagers): the event casts the NURSING PARENT
  (special nursing_parent); the baby is text.  CHILDREN 3-13, TEENS 14-17, ADULTS 18-54, ELDERS 55+ (the collection's
  elder age).  A caregiver, healer or other grown-up the text names is 18+ (a plain "villager" 14+).
- Sex is random in every role (a villager role's "any").  The source names no one, so no text carries a name: a role
  only the gate needs is listed in collection.cast_only.
- Weights (L10461-10463): harmless and minor-setback outcomes are normal (20); serious injury, prolonged illness and
  disappearance are rare (5); a death the source calls "rare" is rare (5).  The source's own sub-branches ("severe
  injury or, on a rare enabled branch, death"; "a rescue, disappearance, or rare fatal accident") are silent
  branches whose pages show one alternative each (node src_cut).
- Effects only where the text clearly gives one: Parenting (small) for caregiving, a small skill for learning or
  practice, health_change for injury and illness (minor -30..-10, serious -60..-40; never kills), kill (cause
  "unknown", the stock "Unknown causes": the owner, 2026-11-14) and vanish (missing, no grave).
- Relationships, pets, traits, reputation, missing-person records and FOLLOW-UP lines are text or ledger notes.
- Designer words inside an outcome ("if eligible", "grant a small appropriate skill gain", "no grave is created
  and a search/missing-person state persists", "selected by weighted sub-branch") are ledger cuts, never shown.
- Kinship (V28 retrofit, 2026-11-14): the four events whose text names a family tie cast it as a relation
  (cie-v6-binary.md 21): 38 "Two parents" and 39 "Longtime partners" spouse_of (the games' nearest: co-parents),
  40 "Two siblings" sibling_of, 51 "A parent ... a child" parent_of.
- Protection: no V27 branch harms a nursing parent, the Golden Child or the VV3 Chief.  The babies' events harm no
  one; every harm-capable role is protected "auto" (keeps those villagers out).

    python scripts/collection_v27.py          # write every file, then python scripts/collection_check.py --format them
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import collection_manifest as cm  # noqa: E402

OUT = lib.COLLECTION_DIR / "v27"
TRADES = ["Building", "Farming", "Healing", "Research"]          # "an appropriate skill": one at random
MINOR, SERIOUS = (-30, -10), (-60, -40)

# Roles
CHILD = {"kind": "villager", "min_age": 3, "max_age": 13}
TEEN = {"kind": "villager", "min_age": 14, "max_age": 17}
ADULT = {"kind": "villager", "min_age": 18, "max_age": 54}
ELDER = {"kind": "villager", "min_age": 55}
GROWN = {"kind": "villager", "min_age": 18}
VILLAGER = {"kind": "villager", "min_age": 14}
NURSING = {"kind": "villager", "min_age": 14, "special": "nursing_parent"}


def skilled(base: dict, skill: str) -> dict:
    return dict(base, skill={"names": [skill], "min": 1})


# Effects (src filled in with the outcome's line)
def par(role):
    return {"do": "skill", "role": role, "skills": ["Parenting"], "min": 5, "max": 10}


def skill(role, skills):
    return {"do": "skill", "role": role, "skills": list(skills), "min": 5, "max": 10}


def hurt(role, size=MINOR):
    return {"do": "health_change", "role": role, "min": size[0], "max": size[1]}


def kill(role):
    return {"do": "kill", "role": role, "cause": "unknown"}


def vanish(role):
    return {"do": "vanish", "role": role}


def damage(size="small"):
    return {"do": "damage", "structures": "any", "size": size}


def T(what, reason):
    return {"what": what, "reason": reason}


def O(effects=(), rarity=None, text_only=(), subs=None, cut=()):
    """One outcome: its effects, rarity, text_only reasons, node cuts (src_cut) or sub-branches [(key, O), ...]."""
    return {"effects": list(effects), "rarity": rarity, "text_only": list(text_only), "subs": subs, "cut": list(cut)}


N0 = O()          # no effect

# num: (roles, cast_only, [A, B, C], ledger cuts [(offset, text, why)], description, intro (effects, text_only))
E = {
    1: ({"parent": NURSING}, [], [O([par("parent")]), N0, O([par("parent")])], [],
        "A baby cries whenever the evening drums begin, and the family looks for a way to settle them.", None),
    2: ({"parent": NURSING, "visitor": VILLAGER}, [], [N0, O([par("visitor")]), O([par("parent")])], [],
        "A baby grabs a visitor's braided hair and will not let go.", None),
    3: ({"parent": NURSING}, [], [N0, O([par("parent")]), N0],
        [(4, " if eligible", "designer condition (nursing is the nursing parent's own state)")],
        "A baby reaches for a familiar villager who has come home after several days away.", None),
    4: ({"parent": NURSING}, [], [O([par("parent")]), N0, O([par("parent")])], [],
        "A crawling baby makes a daring escape from the play mat.", None),
    5: ({"parent": NURSING, "carer": VILLAGER}, [], [O([par("parent")]), O([par("carer")]),
                                                     O([par("parent"), par("carer")])], [],
        "Two caregivers disagree about the best way to soothe a fussy baby.", None),
    6: ({"kid1": CHILD, "kid2": CHILD, "kid3": CHILD}, ["kid2", "kid3"],
        [N0, N0, O([hurt("kid1", SERIOUS)], "rare")], [],
        "Three children slip away to explore without telling their guardians.", None),
    7: ({"child": CHILD, "friend": CHILD}, ["child", "friend"], [N0, N0, N0], [],
        "A child learns that a friend has been hiding a broken keepsake.", None),
    8: ({"joker": CHILD, "hurt": CHILD, "caregiver": GROWN}, ["joker", "hurt"], [N0, N0, O([par("caregiver")])], [],
        "A mischievous child mocks another child's stutter during a game.", None),
    9: ({"ruler1": CHILD, "ruler2": CHILD}, ["ruler1", "ruler2"], [N0, N0, N0], [],
        "The children declare a patch of riverbank an independent kingdom.", None),
    10: ({"child": CHILD}, [], [N0, N0, O([vanish("child")], "rare")], [],
         "A child fails to appear when the evening meal is served.", None),
    11: ({"child": CHILD}, [], [N0, N0, O([hurt("child", SERIOUS)], "rare")], [],
         "A child sets out to prove that a frightening cave legend is true.", None),
    12: ({"child": CHILD}, ["child"], [N0, N0, N0], [],
         "A quiet child is invited to join an established group of friends.", None),
    13: ({"teen1": TEEN, "teen2": TEEN}, ["teen2"], [N0, N0, O([vanish("teen1")], "rare")],
         [(5, "; no grave is created and a search/missing-person state persists",
           "designer rule: missing, not dead (the vanish effect: no grave)")],
         "A group of teenagers launches a homemade raft after dark without permission.", None),
    14: ({"teen": TEEN}, [], [O([skill("teen", ["Research"])]), N0,
                              O(rarity="rare", subs=[
                                  ("injury", O([hurt("teen", SERIOUS)], cut=["death"],
                                               text_only=[T("death", "the rare death is its own sub-branch page")])),
                                  ("death", O([kill("teen")], "rare", cut=["severe injury"],
                                              text_only=[T("injury", "the severe injury is its own sub-branch page")]))])],
         [(5, "or, on a rare enabled branch,", "designer words: the rare death is a weighted sub-branch")],
         "A teenager climbs toward a forbidden overlook to prove a local legend.", None),
    15: ({"teen": TEEN}, ["teen"], [N0, N0, N0], [],
         "A teenager tries an elaborate performance to impress someone they admire.", None),
    16: ({"teen": TEEN}, [], [O([skill("teen", TRADES)]), N0, N0],
         [(3, "; grant a small appropriate skill gain", "instruction: the small skill effect")],
         "A teenager unhappy with their chosen work secretly tries another trade.", None),
    17: ({"teen1": TEEN, "teen2": TEEN}, [], [N0, O([hurt("teen1"), hurt("teen2")]),
                                              O([hurt("teen2", SERIOUS)], "rare")], [],
         "Two teenagers promise each other never to back down from a dare.", None),
    18: ({"teen": TEEN}, ["teen"], [N0, N0, N0], [],
         "A teenager learns that a crush does not return their feelings.", None),
    19: ({"builder": skilled(ADULT, "Building"), "apprentice": VILLAGER, "victim": VILLAGER}, ["apprentice"],
         [O([skill("builder", ["Building"])]), O([damage("small")]),
          O([hurt("victim", SERIOUS), skill("builder", ["Building"])], "rare")], [],
         "A builder ignores an apprentice's warning about a weak hut support.", None),
    20: ({"helper": ADULT}, [], [N0, N0, O([hurt("helper")])], [],
         "An agreeable villager keeps taking on more chores than they can manage.", None),
    21: ({"councilor": ADULT, "colleague": VILLAGER}, ["councilor", "colleague"], [N0, N0, N0], [],
         "A forceful villager dominates a council meeting.", None),
    22: ({"healer": skilled(ADULT, "Healing")}, [], [O([skill("healer", ["Healing"])]), N0, N0], [],
         "A respected healer begins to doubt their own judgment after a difficult case.", None),
    23: ({"worker": ADULT}, [], [N0, N0, O([hurt("worker")])], [],
         "A villager stays awake for days trying to finish a major project.", None),
    24: ({"explorer": ADULT}, [], [O([skill("explorer", ["Research"])]), O([hurt("explorer", SERIOUS)], "rare"),
                                   O([vanish("explorer")], "rare")],
         [(5, " and no grave appears", "designer rule: missing, not dead (the vanish effect: no grave)")],
         "An explorer sets off alone despite warnings about the weather.", None),
    25: ({"elder": ELDER}, [], [N0, N0, O([vanish("elder")], "rare")], [],
         "An elder asks to visit the opposite shore one final time.", None),
    26: ({"elder": ELDER, "apprentice": VILLAGER}, [], [O([skill("elder", TRADES), skill("apprentice", TRADES)]),
                                                        N0, N0], [],
         "An elder refuses to admit that a young apprentice knows a better technique.", None),
    27: ({"elder": ELDER}, ["elder"], [N0, N0, N0], [],
         "An elder keeps a chair free for a longtime companion who has died.", None),
    28: ({"elder": ELDER}, ["elder"], [N0, N0, N0], [],
         "An elder announces a wish to learn something completely new.", None),
    29: ({"elder": ELDER}, ["elder"], [N0, N0, N0], [],
         "An elder remembers a path no one has used in decades.", None),
    30: ({"finder": VILLAGER}, [], [O([skill("finder", ["Healing"])]), N0, N0],
         [(2, " of a randomly selected local species", "designer note: the species is not named")],
         "A villager finds a small injured animal and decides to help it.",
         ([], [T("injured", "the injured one is an animal, not a villager")])),
    31: ({"villager": VILLAGER}, ["villager"], [N0, N0, N0], [],
         "A villager grows attached to a territorial little creature that guards a favorite spot.", None),
    32: ({"swimmer": VILLAGER}, ["swimmer"], [N0, O(text_only=[T("disappears", "the fish disappears, not a villager")]),
                                              N0], [],
         "A swimmer keeps meeting the same fish in the lagoon.", None),
    33: ({"child": CHILD}, ["child"], [N0, N0, N0], [],
         "A child discovers a striking insect.", None),
    34: ({"villager": VILLAGER}, ["villager"], [N0, N0, N0], [],
         "A villager adopts a cute creature that turns out to be noisy, messy and destructive.", None),
    35: ({"guardian": VILLAGER}, ["guardian"],
         [N0, O(text_only=[T("dies", "the pet dies, not a villager")]),
          O(text_only=[T("disappears", "the animal disappears, not a villager")])], [],
         "A beloved old animal companion grows weak with age.", None),
    36: ({"finder": VILLAGER, "naturalist": skilled(GROWN, "Research")}, ["finder"],
         [O([skill("naturalist", ["Research"])]), N0, N0], [],
         "A villager finds an egg or hatchling that seems to have been abandoned.", None),
    37: ({"villager": VILLAGER}, ["villager"], [N0, N0, N0], [],
         "A villager spots a creature they released long ago, near the same tree.", None),
    38: ({"parent1": GROWN, "parent2": dict(GROWN, relation={"spouse_of": "parent1"})}, [],
         [N0, N0, O([par("parent1"), par("parent2")])], [],
         "Two parents disagree over chores, fatigue and how to raise their children.", None),
    39: ({"partner1": GROWN, "partner2": dict(GROWN, relation={"spouse_of": "partner1"})}, ["partner1", "partner2"],
         [N0, N0, N0], [],
         "Longtime partners realize they only ever talk about work.", None),
    40: ({"sibling1": {"kind": "villager", "min_age": 3},
          "sibling2": {"kind": "villager", "min_age": 3, "relation": {"sibling_of": "sibling1"}}},
         ["sibling1", "sibling2"],
         [O(text_only=[T("celebrates", "rule 7: an elder's praise, not a village celebration")]), N0, N0], [],
         "Two siblings compete for praise after finishing different tasks.", None),
    41: ({"friend1": VILLAGER, "friend2": VILLAGER}, ["friend1", "friend2"], [N0, N0, N0], [],
         "Two friends who once promised to stay inseparable forever look at that promise again.", None),
    42: ({"friend1": GROWN, "friend2": GROWN}, ["friend1", "friend2"], [N0, N0, N0],
         [(4, ", if age-eligible", "designer condition: both roles are adults")],
         "Two inseparable villagers find everyone assuming they must be courting.", None),
    43: ({"lover1": GROWN, "lover2": GROWN}, ["lover1", "lover2"], [N0, N0, N0], [],
         "Two lovers disagree about whether one of them should take a dangerous assignment.", None),
    44: ({"suitor": GROWN, "interest": GROWN}, ["suitor", "interest"], [N0, N0, N0], [],
         "A villager tries to impress a romantic interest with an exaggerated story.", None),
    45: ({"researcher1": skilled(GROWN, "Research"), "researcher2": skilled(GROWN, "Research")},
         ["researcher1", "researcher2"], [N0, N0, N0], [],
         "Two researchers resent having to share the credit for a discovery.", None),
    46: ({"ally": GROWN}, ["ally"], [N0, N0, N0], [],
         "A loyal ally publicly opposes a leader's plan.", None),
    47: ({"villager": VILLAGER, "neighbor": VILLAGER}, ["villager", "neighbor"], [N0, N0, N0], [],
         "A villager notices that a neighbor has withdrawn after a loss.", None),
    48: ({"artisan": skilled(GROWN, "Building"), "apprentice": VILLAGER}, ["artisan"],
         [O([skill("apprentice", ["Building"])]), N0, N0], [],
         "A blunt artisan agrees to train an unusually sensitive apprentice.", None),
    49: ({"villager": VILLAGER}, ["villager"], [N0, N0, N0], [],
         "A villager with few living relatives is invited into a household tradition.", None),
    50: ({"friend1": VILLAGER, "friend2": VILLAGER}, ["friend1", "friend2"], [N0, N0, N0], [],
         "A long-absent friend returns, expecting everything to be as it was.", None),
    51: ({"parent": dict(GROWN, relation={"parent_of": "child"}), "child": CHILD}, ["child"],
         [O([par("parent")]), N0, N0], [],
         "A parent realizes they unfairly blamed a child for an accident.", None),
    52: ({"fisher": VILLAGER, "scholar": skilled(VILLAGER, "Research")}, ["fisher", "scholar"], [N0, N0, N0], [],
         "A boisterous fisherman and a quiet scholar are assigned to the same project.", None),
    53: ({"searcher": VILLAGER}, ["searcher"],
         [N0, N0, O(text_only=[T("death", "no death is declared: the family's remembrance only")])], [],
         "A search party finds a missing villager's belongings, but no sign of the person.", None),
    54: ({"explorer1": VILLAGER, "explorer2": VILLAGER}, [],
         [N0, O([hurt("explorer1", SERIOUS)], "rare"), O([kill("explorer1")], "rare")],
         [(5, "A rare enabled outcome results in death;", "designer words: the rare death is this outcome's kill"),
          (5, " without graphic detail", "designer note on tone")],
         "Several explorers come home with an unfamiliar illness.",
         ([hurt("explorer1"), hurt("explorer2")], [])),
    55: ({"diver": VILLAGER, "companion": VILLAGER}, ["companion"],
         [N0, O([skill("diver", ["Research"])]),
          O(subs=[("rescue", O([hurt("diver")], cut=[", disappearance, fatal accident"])),
                  ("missing", O([vanish("diver")], "rare", cut=["a rescue, ", ", fatal accident"])),
                  ("fatal", O([kill("diver")], "rare", cut=["rescue, disappearance, "]))])],
         [(5, ", selected by weighted sub-branch", "designer words: the three are weighted sub-branches"),
          (5, "or rare ", "designer words: the rarity is the sub-branch's weight; each page shows one alternative")],
         "A villager insists the deep pool hides a sacred chamber and wants to dive alone.", None),
    56: ({"crew1": VILLAGER, "crew2": VILLAGER}, [],
         [N0, O([vanish("crew1"), vanish("crew2")], "rare"), O([vanish("crew1"), vanish("crew2")], "rare")],
         [(5, "; relatives can respond in future events", "designer note: a follow-up hook")],
         "A canoe drifts ashore without its crew.", None),
    57: ({"frightened": VILLAGER}, [], [N0, N0, O([hurt("frightened")])], [],
         "An old bell is said to summon spirits if it is rung at midnight.", None),
}

def outcome_text(n: int, cuts: dict[int, list[str]], node_cut: list[str]) -> str:
    p = cc.processed_line(n, cuts, {})
    for c in node_cut:
        got = cc.apply_cut(p, c)
        if got is None:
            raise SystemExit(f"L{n}: src_cut {c!r} not in {p!r}")
        p = got[0]
    return p[:1].upper() + p[1:]


def build(num: int) -> tuple[str, dict]:
    eid, title = cm.V27_EVENTS[num - 1]
    roles, cast_only, outs, lcuts, desc, intro = E[num]
    h = cm.V27_FIRST + 8 * (num - 1)
    L = lambda k: f"L{h + k}"                                       # noqa: E731
    head = lib.normalize_source_text(lib.line(h))
    assert head.split(" - ", 1)[1].strip() == title, (head, title)
    cuts: dict[int, list[str]] = {}
    ledger = [{"src": L(1), "kind": "note", "why": "the cast: " + lib.normalize_source_text(lib.line(h + 1)).split(
        ":", 1)[1].strip().rstrip(".") + " (the roles)"}]
    for off, text, why in lcuts:
        ledger.append({"src": L(off), "kind": "note", "text": text, "why": why})
        cuts.setdefault(h + off, []).append(text)
    ledger.append({"src": L(6), "kind": "note", "why": "FOLLOW-UP: a designer note on saved state, never shown"})

    def eff(lst, line):
        return [dict(e, src=line) for e in lst]

    def tonly(lst, line):
        return [dict(t, src=line) for t in lst]

    nodes: dict = {}
    intro_node = {"name": "The setup", "text": outcome_text(h + 2, cuts, []), "src": L(2)}
    if intro:
        if intro[0]:
            intro_node["effects"] = eff(intro[0], L(2))
        if intro[1]:
            intro_node["text_only"] = tonly(intro[1], L(2))
    kids = []
    nodes["intro"] = intro_node
    any_rare = any(o["rarity"] for o in outs)
    for letter, o, off in zip("abc", outs, (3, 4, 5)):
        child = {"next": letter}
        if any_rare:
            child["weight"] = cc.RARITY_WEIGHTS[o["rarity"]]
            if o["rarity"]:
                child["rarity"] = o["rarity"]
        kids.append(child)
        if o["subs"]:
            sub_rare = any(so["rarity"] for _, so in o["subs"])
            sk = []
            for key, so in o["subs"]:
                c = {"next": f"{letter}_{key}"}
                if sub_rare:
                    c["weight"] = cc.RARITY_WEIGHTS[so["rarity"]]
                    if so["rarity"]:
                        c["rarity"] = so["rarity"]
                sk.append(c)
                nodes[f"{letter}_{key}"] = page(f"Outcome {letter.upper()}: {key}", outcome_text(h + off, cuts, so["cut"]),
                                                L(off), eff(so["effects"], L(off)), tonly(so["text_only"], L(off)),
                                                so["cut"])
            nodes[letter] = {"type": "branch", "children": sk}
        else:
            nodes[letter] = page(f"Outcome {letter.upper()}", outcome_text(h + off, cuts, o["cut"]), L(off),
                                 eff(o["effects"], L(off)), tonly(o["text_only"], L(off)), o["cut"])
    intro_node["children"] = kids
    required = [r for r, v in roles.items() if v.get("kind") == "villager" and not v.get("optional")]
    col = {"id": eid, "title_src": L(0), "ledger": ledger, "description": desc}
    if cast_only:
        col["cast_only"] = list(cast_only)
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": title, "games": [1, 2, 3, 4, 5], "collection": col,
           "requirement": {"min_eligible": len(required)}, "roles": roles, "start": "intro", "nodes": nodes}
    return eid, doc


def page(name, text, src, effects, text_only, cut):
    n = {"name": name, "popup": "append", "join": "paragraph", "text": text, "src": src}
    if cut:
        n["src_cut"] = [{"src": src, "text": c} for c in cut]
    if effects:
        n["effects"] = effects
    if text_only:
        n["text_only"] = text_only
    return n


def main() -> int:
    OUT.mkdir(exist_ok=True)
    assert len(E) == len(cm.V27_EVENTS) == 57
    paths = []
    for num in sorted(E):
        eid, doc = build(num)
        p = OUT / f"{eid}.json"
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        paths.append(str(p))
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])


if __name__ == "__main__":
    sys.exit(main())
