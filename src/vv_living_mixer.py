"""The Living Event Engine's mixer: the owner's bank (data/living_events/bank.json) composed into ordinary version 6
graphs at build time, and packed per game as "Island Event Collection\\living.pak" (docs/event-collection/
living-pack.md, VLEP v1).

* K variants per active seed (LE 120, MC 95; MJ is held), deterministic (each seed's own random stream, seeded from
  its id), with coverage balancing across the whole bank (roles, role pairs, archetypes, approaches, lenses).
* An LE variant: the seed sentence and the frame (two cast villagers, their personalities as pools PA / PB, PB never
  the same word as PA), 3 to 5 choices (the category's choice set, or approaches from different families), each a
  branch to a GOOD (20), an adverse MIXED or BAD (20) and a RARE (2) archetype page.  Archetype pages are shared
  nodes carrying their effects, with automatic lines when they have any.  Variant 0 of a seed with a MIX example is
  that MIX (a MIX that breaks a compatibility rule gets only the documented swaps, MIX_CHANGES).
* An MC variant: the situation's setup, its four approaches (k = 0 in the source order, then other orders) and their
  two authored outcomes each, equally likely.
* Every text is the owner's line (typography made plain) or the frame's joining words (grammar fix
  living-frame-article); every compatibility exclusion (bank compat.exclusions) holds on every variant.

    python src/vv_living_mixer.py            # build, print the counts and pack sizes (writes nothing)
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import re
import struct
import sys
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_cie_graph as cg  # noqa: E402

BANK = ROOT / "data" / "living_events" / "bank.json"
K = 10
# An MC situation's variants only reorder its four approaches (near duplicates of one another, about 2 MB a pack):
# it ships its source order alone (lead, 2026-11-14).
MC_K = 1
GAMES = (1, 2, 3, 4, 5)
ALL_SKILLS = ("Parenting", "Building", "Farming", "Healing", "Research")
W_GOOD, W_ADVERSE, W_RARE = 20, 20, 2           # per choice (living-events.md Q7)
W_ALT = W_GOOD // 2                             # each of a MIX outcome's two equal alternatives (MIX_ALTERNATIVES)
assert W_GOOD == W_ADVERSE == 2 * W_ALT
FAMILIES = ("consult", "act", "relate", "withdraw", "play")
FAM_BIT = {f: 1 << i for i, f in enumerate(FAMILIES)}
FAM_CHOICE_SET = 1 << 5
FAM_MC = 1 << 6
FLAG_MIX, FLAG_SET, FLAG_APPROACHES = 1, 2, 4
GROUP_CODE = {"good": 1, "mixed": 2, "bad": 3, "rare": 4}
NONE16, NONE8 = 0xFFFF, 0xFF
# The owner's Global Editorial Override (item 10): about one third each.  A category's mood is the bank's
# (categories[].mood, mc.categories[].mood); the pack keeps it in the seed record (living-pack.md 2.2).
MOODS = ("warm", "social", "serious")
MOOD_BOOST = 2                                  # a least-seen mood's series weight (living-pack.md 4.1a)
FRAME_TAIL = "disagree about what should happen next. Their status alone does not settle the matter."
# The chief's game words (authoring-rules.md 10): VV3 keeps the owner's words, the other games say the village leader.
CHIEF_WORDS = {
    "Chief": {"3": "The chief", "*": "The village leader"},
    "chiefs_possessive": {"3": "the chief's", "*": "the village leader's"},
    "A_chief": {"3": "A chief", "*": "A village leader"},
    "chief": {"3": "the chief", "*": "the village leader"},
    "village_chief": {"3": "the village chief", "*": "the village leader"},
}
# Choices per approach variant, by k (source rule 5: offer 3-5 choices from different families).
APPROACH_COUNT = {1: 4, 3: 5, 5: 3, 7: 4, 9: 5}

# ---- The MIX examples that break a compatibility rule (lead decision, 2026-11-14) ---------------------------------
# Variant 0 reproduces the MIX but swaps ONLY the offending piece for the nearest compatible one (first in the list
# that every rule allows), and applies the doubled-word grammar fix ("a confident confident novice" -> "a confident
# novice").  Each change is listed in living-events.md section 7.
NEAREST_ROLE = {
    "le_role_teenager": ["le_role_adult_villager"],
    "le_role_child": ["le_role_adult_villager"],
}
NEAREST_ONE_GAME_ROLE = {"le_role_chief": "le_role_council_member"}
# Owner (2026-11-15): archetypes are not bad; no archetype line is replaced.  Where an earlier rule (a compatibility
# swap or a sensitivity edit) changed a piece of a MIX, variant 0 keeps BOTH the owner's original and that replacement
# as two equal alternatives (the run picks one at random): an outcome as two children of half the weight each, a
# personality as a pool of the two words.  The original is always one of the two.  Keys: "<choice><outcome>"
# (0-based) or the frame slot.
MIX_ALTERNATIVES = {
    'MIX-001': {'01': 'le_arc_bad_09', '31': 'le_arc_bad_02'},
    'MIX-005': {'31': 'le_arc_bad_02', 'second': 'le_pers_thoughtful'},
    'MIX-006': {'30': 'le_arc_good_02'},
    'MIX-007': {'01': 'le_arc_bad_07', 'second': 'le_pers_stubborn'},
    'MIX-008': {'first': 'le_pers_thoughtful', 'second': 'le_pers_cautious'},
    'MIX-009': {'00': 'le_arc_good_07', '20': 'le_arc_good_02'},
    'MIX-010': {'31': 'le_arc_bad_02'},
    'MIX-015': {'21': 'le_arc_bad_09'},
    'MIX-016': {'01': 'le_arc_bad_09', '10': 'le_arc_good_07', '30': 'le_arc_good_02', '31': 'le_arc_bad_02'},
    'MIX-020': {'21': 'le_arc_bad_09'},
    'MIX-021': {'first': 'le_pers_cautious'},
    'MIX-022': {'01': 'le_arc_bad_07'},
    'MIX-023': {'11': 'le_arc_mixed_04'},
    'MIX-025': {'00': 'le_arc_good_02'},
    'MIX-027': {'second': 'le_pers_thoughtful'},
    'MIX-029': {'20': 'le_arc_good_02'},
    'MIX-030': {'21': 'le_arc_bad_09', '30': 'le_arc_good_07'},
    'MIX-031': {'01': 'le_arc_bad_09', '11': 'le_arc_bad_02', '31': 'le_arc_bad_02'},
    'MIX-032': {'01': 'le_arc_bad_07'},
    'MIX-033': {'second': 'le_pers_devout'},
    'MIX-035': {'31': 'le_arc_bad_02'},
    'MIX-037': {'11': 'le_arc_bad_02'},
    'MIX-038': {'first': 'le_pers_devout'},
    'MIX-040': {'10': 'le_arc_good_07', '30': 'le_arc_good_07'},
    'MIX-042': {'10': 'le_arc_good_02', '11': 'le_arc_bad_02', '31': 'le_arc_mixed_04'},
    'MIX-045': {'first': 'le_pers_cautious'},
    'MIX-047': {'01': 'le_arc_bad_07'},
    'MIX-050': {'21': 'le_arc_bad_09'},
    'MIX-051': {'second': 'le_pers_thoughtful'},
    'MIX-052': {'01': 'le_arc_bad_07', '11': 'le_arc_bad_02', '20': 'le_arc_good_07'},
    'MIX-053': {'11': 'le_arc_mixed_04', 'second': 'le_pers_thoughtful'},
    'MIX-055': {'second': 'le_pers_stubborn'},
    'MIX-056': {'first': 'le_pers_thoughtful', 'second': 'le_pers_cautious'},
    'MIX-057': {'second': 'le_pers_devout'},
}
ALT_RULE = "both kept, equal chance (owner, 2026-11-15)"


# ---- What the mixer never combines (owner decision, 2026-11-15) ----------------------------------------------------
# The mixer keeps everything except combinations that produce obviously problematic power dynamics, invalidate
# someone's pain or trauma, portray anyone as lesser, or a minor-adult romance or power imbalance; genuine
# contradictions stay prevented (coherence).  The bank's compat table (C3, C6, C9, P1-P4) holds the rest.
SENSITIVITY_RULES = {
    "S7": "A romantic, secret-keeping or coercive frame (the adult-only seeds, a friend's secret, an elder demanding "
          "obedience, the choice to keep the matter private) casts adults only: both villagers 18 or older, never a "
          "child, a teenager or anyone younger than 18 in any role (no minor-adult romance or power imbalance).",
    "S17": "A seed about love, a couple, a family's view of a companion, or a villager who is alone never has the "
           "chief decide for them (an obviously problematic power dynamic).",
}
# Love, a couple, a family's view of a companion, being alone: nobody in authority decides for them (S17).
RELATIONSHIP_SEEDS = {"le_fam_05", "le_fam_06", "le_fam_07", "le_foo_07", "le_emo_04"}
ADULT_FRAME_SEEDS = {"le_fam_04", "le_gov_08"}      # plus every seed tagged adult_only
SECRET_CHOICES = {"le_app_withdraw_03"}              # Keep the matter private
ADULT_AGE = 18


def plain(text: str) -> str:
    """Typography made plain (authoring-rules.md 4.1)."""
    for a, b in (("—", " - "), ("–", "-"), ("‘", "'"), ("’", "'"), ("“", '"'),
                 ("”", '"'), ("…", "..."), ("ç", "c"), ("é", "e")):
        text = text.replace(a, b)
    return text


def title_case(heading: str) -> str:
    """A category heading as its title (the bank's rule: small words lower case except first)."""
    small = {"and", "or", "of", "the", "a", "an", "in", "on", "at", "to", "for"}
    words = heading.lower().split(" ")
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def stream_for(key: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(key.encode("ascii")).digest()[:8], "little"))


# ---- The bank -------------------------------------------------------------------------------------------------------


class Bank:
    def __init__(self, path: Path | str = BANK):
        self.path = Path(path)
        self.raw = json.loads(self.path.read_text(encoding="utf-8"))
        b = self.raw
        self.credit = b["credit"]["text"]
        self.categories = b["categories"]
        self.cat = {c["id"]: c for c in self.categories}
        self.seeds = b["seeds"]
        self.seed = {s["id"]: s for s in self.seeds}
        self.roles = b["roles"]
        self.role = {r["id"]: r for r in self.roles}
        self.role_index = {r["id"]: i for i, r in enumerate(self.roles)}
        self.pers = b["personalities"]
        self.per = {p["id"]: p for p in self.pers}
        self.lenses = b["lenses"]
        self.approaches = b["approaches"]
        self.app = {a["id"]: a for a in self.approaches}
        self.archetypes = b["archetypes"]
        self.arc = {a["id"]: a for a in self.archetypes}
        self.arc_index = {a["id"]: i for i, a in enumerate(self.archetypes)}
        self.choice_sets = {c["id"]: c for c in b["choice_sets"]}
        self.choice = {c["id"]: c for c in b["choices"]}
        self.mix = b["mix"]
        self.mix_by_seed = {m["seed"]: m for m in self.mix}
        ex = b["compat"]["exclusions"]
        self.ex = {k: {kk: set(vv) for kk, vv in v.items()} for k, v in ex.items()}
        self.conflicts = {c["mix"]: c["conflicts"] for c in b["compat"]["owner_example_conflicts"]}
        self.mc = b["mc"]
        self.mc_cats = self.mc["categories"]
        self.mc_cat = {c["id"]: c for c in self.mc_cats}
        self.mc_sits = self.mc["situations"]

    # -- compatibility (bank compat.exclusions) --
    def seed_allows(self, seed: str, kind: str, item: str) -> bool:
        key = {"approach": "seed_approach", "choice": "seed_choice", "archetype": "seed_archetype",
               "role": "seed_role"}[kind]
        return item not in self.ex[key].get(seed, set())

    def role_allows_personality(self, role: str, pers: str) -> bool:
        return pers not in self.ex["role_personality"].get(role, set())

    def role_allows_archetype(self, role: str, arc: str) -> bool:
        return arc not in self.ex["role_archetype"].get(role, set())


def role_games(bank: Bank, rid: str) -> set[int]:
    return set(bank.role[rid]["games"])


def is_stranger(bank: Bank, rid: str) -> bool:
    return bank.role[rid]["cast"]["kind"] == "stranger"


# ---- Variants -------------------------------------------------------------------------------------------------------


@dataclass
class Variant:
    seed: str                         # the bank id (le_per_01, mc_isl_01)
    manifest_id: str                  # living_le_per_01
    series: str                       # living_le_per
    bank: int                         # 0 LE, 1 MC
    cat_index: int
    seed_index: int
    k: int
    games: list[int]
    flags: int
    role_a: int = NONE16
    role_b: int = NONE16
    lens: int = NONE8
    family: int = 0
    graph: dict = field(default_factory=dict)
    outcomes: list[tuple[str, int, int]] = field(default_factory=list)    # (node, group, archetype index)
    plan: dict = field(default_factory=dict)                              # what was chosen (tests, the report)
    cieg: bytes = b""
    mood: int = 0                     # MOODS index of the seed's category


def _pick(cands, score, rng: random.Random):
    """The candidate with the lowest score; ties broken by the seed's stream (deterministic)."""
    cands = list(cands)
    if not cands:
        return None
    best = min(score(c) for c in cands)
    ties = sorted(c for c in cands if score(c) == best)
    return ties[rng.randrange(len(ties))]


def personality_item(bank: Bank, pid: str) -> str:
    p = bank.per[pid]
    return f"{p['article']} {p['text']}"


def frame_part(bank: Bank, role_id: str, pers: str | None, pool: str | None) -> str:
    """'a warm master parent', '{PA} master parent' or, after the doubled-word fix, 'a confident novice'."""
    word = bank.role[role_id]["word"]
    if pool:
        return f"{{{pool}}} {word}"
    if pers is None:
        return f"{bank.role[role_id]['article']} {word}"
    return f"{personality_item(bank, pers)} {word}"


def seed_text(bank: Bank, seed: dict) -> tuple[str, dict]:
    """The seed sentence (plain), with the chief's game words; and the words it uses."""
    text = plain(seed["text"])
    words = {}
    for src_words, name in seed.get("chief_words") or []:
        src_words = plain(src_words)
        if src_words not in text:
            raise ValueError(f"{seed['code']}: {src_words!r} is not in the seed")
        text = text.replace(src_words, "{@" + name + "}", 1)
        words[name] = CHIEF_WORDS[name]
    return text, words


def label_text(bank: Bank, kind: str, ident: str) -> tuple[str, dict]:
    if kind == "approach":
        text = plain(bank.app[ident]["text"])
        if "chief" in bank.app[ident]["tags"]:
            if "the chief" not in text:
                raise ValueError(ident)
            return text.replace("the chief", "{@chief}"), {"chief": CHIEF_WORDS["chief"]}
        return text, {}
    return plain(bank.choice[ident]["text"]), {}


def words_for(words: dict, games: list[int]) -> dict:
    out = {}
    for name, vals in words.items():
        v = {}
        if 3 in games:
            v["3"] = vals["3"]
        if any(g != 3 for g in games):
            v["*"] = vals["*"]
        out[name] = v
    return out


def resolve_role(bank: Bank, which: str, a: str, b: str) -> str | None:
    """An archetype's abstract role -> 'first' / 'second' (None: not cast, or a stranger: no effect)."""
    if which == "first":
        out = "first"
    elif which == "second":
        out = "second"
    elif which == "junior":
        out = "first"
        for name, rid in (("first", a), ("second", b)):
            if "novice" in bank.role[rid]["tags"] and not is_stranger(bank, rid):
                out = name
                break
    elif which == "elder":
        out = None
        for name, rid in (("first", a), ("second", b)):
            if "elder" in bank.role[rid]["tags"] and not is_stranger(bank, rid):
                out = name
                break
        if out is None:
            return None
    else:
        raise ValueError(which)
    rid = a if out == "first" else b
    return None if is_stranger(bank, rid) else out


def skills_for(games: list[int]) -> list[str]:
    return list(ALL_SKILLS) + (["Devotion"] if 5 in games else [])


def archetype_effects(bank: Bank, arc: str, a: str, b: str, games: list[int]) -> list[dict]:
    out = []
    for e in bank.arc[arc]["effects"]:
        e = dict(e)
        if "role" in e:
            r = resolve_role(bank, e["role"], a, b)
            if r is None:
                continue
            e["role"] = r
        if e.get("skills") == "any":
            e["skills"] = skills_for(games)
        out.append(e)
    return out


def archetype_possible(bank: Bank, seed: str, arc: str, a: str, b: str) -> bool:
    """The bank's compat table, and coherence: an outcome naming an elder needs an elder in the scene."""
    if not bank.seed_allows(seed, "archetype", arc):
        return False
    if not (bank.role_allows_archetype(a, arc) and bank.role_allows_archetype(b, arc)):
        return False
    if "needs_elder" in bank.arc[arc]["tags"] and resolve_role(bank, "elder", a, b) is None:
        return False
    return True


def minor_role(bank: Bank, rid: str) -> bool:
    """A role whose villager is always under 18 (a child, a teenager)."""
    return any(t in bank.role[rid]["tags"] for t in ("child", "teen"))


def adult_seed(seed: dict) -> bool:
    return "adult_only" in seed["tags"] or seed["id"] in ADULT_FRAME_SEEDS


def adult_frame(seed: dict, choices) -> bool:
    """S7: a romantic, secret-keeping or coercive frame: both villagers 18 or older."""
    return adult_seed(seed) or any(ident in SECRET_CHOICES for _kind, ident in choices)


HARMFUL = ("kill", "vanish", "die_unrecovered", "baby_lost", "sick")


def harmful(e: dict) -> bool:
    do = e["do"]
    return (do in HARMFUL or (do == "health_change" and e.get("min", 0) < 0) or (do == "mood" and e.get("mood") == "bad")
            or (do == "skill" and (e.get("loss") or (e.get("min") or 0) < 0))
            or (do == "preference" and (e.get("list") == "dislikes" or "dislike" in e)))


def role_spec(bank: Bank, rid: str, allow: bool, adults_only: bool = False) -> dict:
    cast = dict(bank.role[rid]["cast"])
    if cast["kind"] == "stranger":
        return {"kind": "stranger", "sex": cast.get("sex", "random"), "named": True}
    spec = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cast.items()}
    if adults_only and not spec.get("special"):
        # S7: a romantic, secret-keeping or coercive frame casts adults only.
        if spec.get("max_age") and spec["max_age"] < ADULT_AGE:
            raise ValueError(f"{rid}: a minor's role in an adults-only frame")
        spec["min_age"] = max(spec.get("min_age", 14), ADULT_AGE)
    if "skill" in spec:
        spec["skill"] = {k: (list(v) if isinstance(v, list) else v) for k, v in spec["skill"].items()}
    if allow:
        spec["protected"] = "allow"
    return spec


def compose_le(bank: Bank, seed: dict, a: str, b: str, pers_a, pers_b, choices: list[tuple[str, str]],
               outcomes: list[tuple[str, str, str]], games: list[int]) -> tuple[dict, list[tuple[str, int, int]]]:
    """The variant's graph.  pers_a / pers_b: a personality id (fixed, a MIX), None (the doubled-word fix: no
    personality word), "pool" (the PA / PB pool) or a list of ids (a MIX's equal alternatives, a pool of them).
    choices: (kind, id).  outcomes[i]: (good, adverse, rare); good and adverse may be a tuple of two equal
    alternatives (MIX_ALTERNATIVES), each child then weighs W_ALT."""
    text, words = seed_text(bank, seed)
    pools = {}
    for name, rid, pers in (("PA", a, pers_a), ("PB", b, pers_b)):
        if pers == "pool":
            pools[name] = {"items": [personality_item(bank, p["id"]) for p in bank.pers
                                     if bank.role_allows_personality(rid, p["id"])]}
        elif isinstance(pers, list):
            pools[name] = {"items": [personality_item(bank, p) for p in pers]}
        else:
            continue
        if name == "PB" and "PA" in pools:
            pools["PB"]["distinct_from"] = ["PA"]

    def part(rid: str, pers, name: str) -> str:
        if pers == "pool" or isinstance(pers, list):
            return frame_part(bank, rid, None, name)
        return frame_part(bank, rid, pers, None)
    setup = f"{text} (first), {part(a, pers_a, 'PA')}, and (second), {part(b, pers_b, 'PB')}, {FRAME_TAIL}"
    nodes: dict = {}
    q_choices = []
    used_arcs: list[str] = []
    for i, ((kind, ident), (good, adverse, rare)) in enumerate(zip(choices, outcomes)):
        label, w = label_text(bank, kind, ident)
        words.update(w)
        q_choices.append({"label": label, "next": f"c{i + 1}"})
        kids = []
        for slot, weight in ((good, W_GOOD), (adverse, W_ADVERSE)):
            alts = list(slot) if isinstance(slot, tuple) else [slot]
            kids += [{"next": "o_" + x[7:], "weight": weight // len(alts)} for x in alts]
        if rare:
            kids.append({"next": "o_" + rare[7:], "weight": W_RARE})
        for x in [y for s in (good, adverse, rare) for y in (s if isinstance(s, tuple) else (s,))]:
            if x and x not in used_arcs:
                used_arcs.append(x)
        nodes[f"c{i + 1}"] = {"type": "branch", "children": kids}
    allow = {"first": False, "second": False}
    for arc in used_arcs:
        effects = archetype_effects(bank, arc, a, b, games)
        node = {"text": plain(bank.arc[arc]["text"])}
        if effects:
            node["effects"] = effects
            node["auto_text"] = True
            for e in effects:
                if harmful(e) and e.get("role") in allow and bank.arc[arc]["protection"] == "allow":
                    allow[e["role"]] = True
        nodes["o_" + arc[7:]] = node
    graph = {
        "format": "vvfp-cie-graph", "version": 6,
        "title": bank.cat[seed["category"]]["title"],
        "games": sorted(games),
        "roles": {"first": role_spec(bank, a, allow["first"], adult_frame(seed, choices)),
                  "second": role_spec(bank, b, allow["second"], adult_frame(seed, choices))},
    }
    if words:
        graph["words"] = words_for(words, games)
    if pools:
        graph["pools"] = pools
    graph["start"] = "setup"
    graph["nodes"] = {"setup": {"type": "question", "text": setup, "choices": q_choices}, **nodes}
    outs = [("o_" + arc[7:], GROUP_CODE[bank.arc[arc]["group"]], bank.arc_index[arc]) for arc in used_arcs]
    return graph, outs


# ---- LE: the MIX as variant 0 ---------------------------------------------------------------------------------------


def mix_plan(bank: Bank, mix: dict) -> tuple[dict, list[dict]]:
    """The MIX's own pieces, with only the documented swaps for a MIX that breaks a rule; and the changes."""
    seed = mix["seed"]
    a, b = mix["first"]["role"], mix["second"]["role"]
    pa, pb = mix["first"]["personality"], mix["second"]["personality"]
    choices = [("choice", c["choice"]) for c in mix["choices"]]
    outs = [[o[0]["archetype"], o[1]["archetype"]] for o in mix["outcomes"]]
    changes: list[dict] = []
    for conflict in bank.conflicts.get(mix["id"], []):
        m = re.fullmatch(r"(seed|role (\S+)) x (role|archetype|personality) (\S+)", conflict)
        if not m:
            raise ValueError(conflict)
        left_role, kind, item = m.group(2), m.group(3), m.group(4)
        if kind == "role":                                   # seed x role: swap the role
            for slot in ("first", "second"):
                cur = a if slot == "first" else b
                if cur != item:
                    continue
                new = next(r for r in NEAREST_ROLE[item] if bank.seed_allows(seed, "role", r))
                changes.append({"mix": mix["code"], "what": f"{slot} villager's role", "before": bank.role[item]["text"],
                                "after": bank.role[new]["text"], "rule": conflict})
                if slot == "first":
                    a = new
                else:
                    b = new
        elif kind == "personality":                          # role x personality
            rword = bank.role[left_role]["word"]
            ptext = bank.per[item]["text"]
            slot = "first" if (a == left_role and pa == item) else "second"
            if ptext in rword.split():
                # The doubled word ("a confident confident novice"): the grammar fix drops the repeat.
                changes.append({"mix": mix["code"], "what": f"{slot} villager (doubled word, grammar fix)",
                                "before": f"a {ptext} {bank.role[left_role]['text']}",
                                "after": bank.role[left_role]["text"], "rule": conflict})
                if slot == "first":
                    pa = None
                else:
                    pb = None
            else:
                raise ValueError(f"{mix['code']}: {conflict} has no documented change")
        else:
            raise ValueError(f"{mix['code']}: {conflict} has no documented change")
    if not variant_games(bank, bank.seed[seed], a, b):
        # No game has both roles (the VV3 chief with a VV5 practitioner, MIX-027 and MIX-057): the chief becomes
        # the nearest leader role every game has, so the MIX can be shown where its practitioner lives.
        for slot in ("first", "second"):
            cur = a if slot == "first" else b
            if cur in NEAREST_ONE_GAME_ROLE:
                new = NEAREST_ONE_GAME_ROLE[cur]
                changes.append({"mix": mix["code"], "what": f"{slot} villager's role", "before": bank.role[cur]["text"],
                                "after": bank.role[new]["text"],
                                "rule": "no game has both roles (the chief is VV3 only, the practitioners VV5 only)"})
                if slot == "first":
                    a = new
                else:
                    b = new
                break
    # The owner's original and the earlier replacement, both kept as equal alternatives (MIX_ALTERNATIVES).
    alt_outs: dict[tuple[int, int], str] = {}
    alt_pers: dict[str, str] = {}
    for key, new in MIX_ALTERNATIVES.get(mix["code"], {}).items():
        if key in ("first", "second"):
            cur, role, other = (pa, a, pb) if key == "first" else (pb, b, pa)
            if new in (cur, other) or not bank.role_allows_personality(role, new):
                raise ValueError(f"{mix['code']}: {key} alternative {new}")
            alt_pers[key] = new
            changes.append({"mix": mix["code"], "what": f"{key} villager's personality (alternative)",
                            "before": bank.per[cur]["text"], "after": bank.per[new]["text"], "rule": ALT_RULE})
        else:
            i, j = int(key[0]), int(key[1])
            arc = outs[i][j]
            if new == arc or bank.arc[new]["group"] not in (("good",) if j == 0 else ("mixed", "bad")) \
                    or not archetype_possible(bank, seed, new, a, b):
                raise ValueError(f"{mix['code']}: outcome {key} alternative {new}")
            alt_outs[(i, j)] = new
            changes.append({"mix": mix["code"], "what": f"choice {'ABCD'[i]} outcome {j + 1} (alternative)",
                            "before": bank.arc[arc]["text"], "after": bank.arc[new]["text"], "rule": ALT_RULE})
    return {"a": a, "b": b, "pa": pa, "pb": pb, "choices": choices, "outs": outs,
            "alt_outs": alt_outs, "alt_pers": alt_pers}, changes


MIX_CHANGES: list[dict] = []        # filled by generate(): every change the conflicting MIX get


# ---- LE: generated variants -----------------------------------------------------------------------------------------


class Usage:
    """Coverage counters across the whole bank (each seed's choices bias toward what is used least)."""

    def __init__(self) -> None:
        self.c: Counter = Counter()

    def __getitem__(self, key) -> int:
        return self.c[key]

    def add(self, *keys) -> None:
        for k in keys:
            self.c[k] += 1


def variant_games(bank: Bank, seed: dict, a: str, b: str) -> list[int]:
    return sorted(set(seed["games"]) & role_games(bank, a) & role_games(bank, b))


def possible_pair(bank: Bank, seed: dict, a: str, b: str) -> bool:
    return (a != b and not is_stranger(bank, a) and bank.seed_allows(seed["id"], "role", a)
            and bank.seed_allows(seed["id"], "role", b) and bool(variant_games(bank, seed, a, b))
            and not (adult_seed(seed) and (minor_role(bank, a) or minor_role(bank, b))))


def choice_set_choices(bank: Bank, seed: dict) -> list[tuple[str, str]]:
    cs = bank.choice_sets[bank.cat[seed["category"]]["choice_set"]]
    out = [("choice", c) for c in cs["choices"] if bank.seed_allows(seed["id"], "choice", c)]
    if seed["consent_choice_required"] and not any("consent" in bank.choice[c]["tags"] or
                                                   bank.choice[c]["text"].startswith("Ask what the person")
                                                   for _k, c in out):
        out.append(("approach", "le_app_consult_03"))      # Seek the affected person's wishes
    return out


def consent_choice(bank: Bank, kind: str, ident: str) -> bool:
    if kind == "approach":
        return bank.app[ident]["kind"] == "consent"
    return "consent" in bank.choice[ident]["tags"]


def approach_allowed(bank: Bank, seed: dict, ident: str, a: str, b: str) -> bool:
    """The bank's seed x approach exclusions, S7 (no secret-keeping with a child or a teenager) and S17."""
    if not bank.seed_allows(seed["id"], "approach", ident):
        return False
    if ident in SECRET_CHOICES and (minor_role(bank, a) or minor_role(bank, b)):
        return False                                # S7
    if seed["id"] in RELATIONSHIP_SEEDS and bank.app[ident]["kind"] == "authority":
        return False                                # S17: the chief never decides who they love or whether to have a child
    return True


def approach_choices(bank: Bank, seed: dict, n: int, use: Usage, local: Counter, rng: random.Random,
                     a: str, b: str):
    by_fam: dict[str, list[str]] = {f: [] for f in FAMILIES}
    for ap in bank.approaches:
        if approach_allowed(bank, seed, ap["id"], a, b):
            by_fam[ap["family"]].append(ap["id"])
    fams = [f for f in FAMILIES if by_fam[f]]
    n = min(n, len(fams))
    chosen_fams: list[str] = []
    for _ in range(n):
        f = _pick([x for x in fams if x not in chosen_fams], lambda x: use[("fam", x)] + 3 * local[("fam", x)], rng)
        chosen_fams.append(f)
    chosen_fams.sort(key=FAMILIES.index)
    out = []
    for f in chosen_fams:
        ap = _pick(by_fam[f], lambda x: use[("app", x)] + 4 * local[("app", x)], rng)
        out.append(ap)
    if seed["consent_choice_required"] and not any(bank.app[x]["kind"] == "consent" for x in out):
        consent = [x for x in ("le_app_consult_03", "le_app_relate_08") if bank.seed_allows(seed["id"], "approach", x)]
        cons = _pick(consent, lambda x: use[("app", x)] + 4 * local[("app", x)], rng)
        fam = bank.app[cons]["family"]
        if fam in chosen_fams:
            out[chosen_fams.index(fam)] = cons
        else:
            out[-1] = cons
            chosen_fams[-1] = fam
    return [("approach", x) for x in out]


def pick_outcomes(bank: Bank, seed: str, a: str, b: str, choices: list[tuple[str, str]], use: Usage, local: Counter,
                  rng: random.Random, fixed: list[list[str]] | None = None) -> list[tuple[str, str, str]]:
    ok = [x["id"] for x in bank.archetypes if archetype_possible(bank, seed, x["id"], a, b)]
    goods = [x for x in ok if bank.arc[x]["group"] == "good"]
    adverse = [x for x in ok if bank.arc[x]["group"] in ("mixed", "bad")]
    rares = [x for x in ok if bank.arc[x]["group"] == "rare"]
    out = []
    in_variant: Counter = Counter()

    def score(x):
        return use[("arc", x)] + 3 * local[("arc", x)] + 50 * in_variant[x]

    for i in range(len(choices)):
        if fixed is not None:
            g, d = fixed[i]
        else:
            g = _pick(goods, score, rng)
            in_variant[g] += 1
            d = _pick(adverse, score, rng)
            in_variant[d] += 1
        r = _pick(rares, score, rng)
        if r:
            in_variant[r] += 1
        out.append((g, d, r))
    if fixed is None and all(bank.arc[g]["effects"] and bank.arc[d]["effects"] for g, d, _r in out):
        # At least one path with no effect (quality D): the last choice's adverse page becomes an effect-free one.
        free = [x for x in adverse if not bank.arc[x]["effects"]]
        g, d, r = out[-1]
        out[-1] = (g, _pick(free, score, rng), r)
    return out


def le_variants(bank: Bank, seed: dict, k_total: int, use: Usage) -> list[Variant]:
    rng = stream_for(seed["id"])
    local: Counter = Counter()
    cat = bank.cat[seed["category"]]
    cat_index = bank.categories.index(cat)
    seed_index = bank.seeds.index(seed)
    base = dict(seed=seed["id"], manifest_id="living_" + seed["id"], series="living_le_" + cat["code"].lower(),
                bank=0, cat_index=cat_index, seed_index=seed_index)
    out: list[Variant] = []
    limited = 0                      # variants cast with a one-game role (the VV3 chief, the VV5 practitioners)
    mix = bank.mix_by_seed.get(seed["id"])
    for k in range(k_total):
        if k == 0 and mix is not None:
            plan, changes = mix_plan(bank, mix)
            MIX_CHANGES.extend(changes)
            a, b = plan["a"], plan["b"]
            games = variant_games(bank, seed, a, b)
            outs = pick_outcomes(bank, seed["id"], a, b, plan["choices"], use, local, rng, fixed=plan["outs"])
            alt = plan["alt_outs"]
            shown = [tuple((x, alt[(i, j)]) if (i, j) in alt else x for j, x in enumerate((g, d))) + (r,)
                     for i, (g, d, r) in enumerate(outs)]
            pers = [[p, plan["alt_pers"][slot]] if slot in plan["alt_pers"] else p
                    for slot, p in (("first", plan["pa"]), ("second", plan["pb"]))]
            graph, onodes = compose_le(bank, seed, a, b, pers[0], pers[1], plan["choices"], shown, games)
            v = Variant(k=k, games=games, flags=FLAG_MIX | FLAG_SET, role_a=bank.role_index[a],
                        role_b=bank.role_index[b], lens=NONE8, family=FAM_CHOICE_SET, graph=graph, outcomes=onodes,
                        plan={"roles": [a, b], "personalities": [plan["pa"], plan["pb"]], "choices": plan["choices"],
                              "outcomes": outs, "alternatives": sorted(set(alt.values())),
                              "alt_personalities": dict(plan["alt_pers"]), "mix": mix["id"], "changes": changes},
                        **base)
        else:
            pairs = [(x["id"], y["id"]) for x in bank.roles for y in bank.roles
                     if possible_pair(bank, seed, x["id"], y["id"])]
            if limited:
                pairs = [p for p in pairs if len(variant_games(bank, seed, *p)) == len(seed["games"])] or pairs

            def pair_score(p):
                a_, b_ = p
                return (use[("role", a_)] + use[("role", b_)] + 3 * use[("pair", min(p), max(p))]
                        + 6 * (local[("role", a_)] + local[("role", b_)]))
            a, b = _pick(pairs, pair_score, rng)
            games = variant_games(bank, seed, a, b)
            if len(games) < len(seed["games"]):
                limited += 1
            approaches = k % 2 == 1
            if approaches:
                choices = approach_choices(bank, seed, APPROACH_COUNT.get(k, 4), use, local, rng, a, b)
                family = 0
                for kind, ident in choices:
                    family |= FAM_BIT[bank.app[ident]["family"]] if kind == "approach" else FAM_CHOICE_SET
                flags = FLAG_APPROACHES
            else:
                choices = choice_set_choices(bank, seed)
                family = FAM_CHOICE_SET | sum({FAM_BIT[bank.app[i]["family"]] for kd, i in choices if kd == "approach"})
                flags = FLAG_SET
            lens = _pick(range(len(bank.lenses)), lambda x: use[("lens", x)] + 4 * local[("lens", x)], rng)
            outs = pick_outcomes(bank, seed["id"], a, b, choices, use, local, rng)
            graph, onodes = compose_le(bank, seed, a, b, "pool", "pool", choices, outs, games)
            v = Variant(k=k, games=games, flags=flags, role_a=bank.role_index[a], role_b=bank.role_index[b],
                        lens=lens, family=family, graph=graph, outcomes=onodes,
                        plan={"roles": [a, b], "personalities": ["pool", "pool"], "choices": choices,
                              "outcomes": outs, "lens": lens}, **base)
            use.add(("lens", lens))
            local[("lens", lens)] += 1
        a, b = v.plan["roles"]
        use.add(("role", a), ("role", b), ("pair", min(a, b), max(a, b)))
        local[("role", a)] += 1
        local[("role", b)] += 1
        for kind, ident in v.plan["choices"]:
            if kind == "approach":
                use.add(("app", ident), ("fam", bank.app[ident]["family"]))
                local[("app", ident)] += 1
                local[("fam", bank.app[ident]["family"])] += 1
        for trio in v.plan["outcomes"]:
            for x in trio:
                if x:
                    use.add(("arc", x))
                    local[("arc", x)] += 1
        out.append(v)
    return out


# ---- MC -------------------------------------------------------------------------------------------------------------


def mc_orders(sit: dict, k_total: int) -> list[tuple[int, ...]]:
    n = len(sit["approaches"])
    perms = [p for p in itertools.permutations(range(n)) if p != tuple(range(n))]
    rng = stream_for(sit["id"])
    rng.shuffle(perms)
    return [tuple(range(n))] + perms[:max(0, k_total - 1)]


def mc_subject(sit: dict) -> dict:
    s = dict(sit["subject"])
    if s["kind"] == "stranger":
        return {"kind": "stranger", "sex": s.get("sex", "random")}
    return s


def compose_mc(bank: Bank, sit: dict, order: tuple[int, ...]) -> tuple[dict, list[tuple[str, int, int]]]:
    games = sorted(sit["games"])
    nodes: dict = {}
    choices = []
    outs = []
    harmed_allow = False
    words: dict = {}

    def t(text: str) -> str:
        out, w = mc_text(text)
        words.update(w)
        return out
    for pos, i in enumerate(order):
        ap = sit["approaches"][i]
        choices.append({"label": t(ap["text"]), "next": f"c{ap['letter'].lower()}"})
    for i, ap in enumerate(sit["approaches"]):
        kids = []
        for j, o in enumerate(ap["outcomes"]):
            name = f"o_{ap['letter'].lower()}{j + 1}"
            node = {"text": t(o["text"])}
            effects = []
            for e in o["effects"]:
                e = dict(e)
                if e.get("skills") == "any":
                    e["skills"] = skills_for(games)
                effects.append(e)
                if harmful(e) and o["protection"] == "allow":
                    harmed_allow = True
            if effects:
                node["effects"] = effects
                node["auto_text"] = True
            nodes[name] = node
            kids.append({"next": name, "weight": int(o.get("weight", 1))})
            outs.append((name, 1 if j == 0 else 3, NONE8))
        nodes[f"c{ap['letter'].lower()}"] = {"type": "branch", "children": kids}
    subject = mc_subject(sit)
    if harmed_allow and subject["kind"] == "villager":
        subject["protected"] = "allow"
    setup = t(sit["text"])
    graph = {"format": "vvfp-cie-graph", "version": 6,
             "title": mc_title(bank.mc_cat[sit["category"]]["heading"]),
             "games": games, "roles": {"subject": subject}}
    if words:
        graph["words"] = words_for(words, games)
    graph.update({"start": "setup",
                  "nodes": {"setup": {"type": "question", "text": setup, "choices": choices}, **nodes}})
    return graph, outs


MC_CHIEF = (("the village chief", "village_chief"), ("the chief", "chief"))


def mc_text(text: str) -> tuple[str, dict]:
    """An MC line (plain), the chief written as the game word outside VV3 (authoring-rules.md 10)."""
    text = plain(text)
    words = {}
    for src_words, name in MC_CHIEF:
        if src_words in text:
            text = text.replace(src_words, "{@" + name + "}")
            words[name] = CHIEF_WORDS[name]
    return text, words


def mc_title(heading: str) -> str:
    """The MC category's title: its heading in title case, "&" written "and" (no game's title can show "&"; grammar
    fix living-title-ampersand)."""
    return title_case(plain(heading)).replace(" & ", " and ")


def mc_variants(bank: Bank, sit: dict, k_total: int) -> list[Variant]:
    cat = bank.mc_cat[sit["category"]]
    out = []
    for k, order in enumerate(mc_orders(sit, k_total)):
        graph, outs = compose_mc(bank, sit, order)
        out.append(Variant(seed=sit["id"], manifest_id="living_" + sit["id"], series="living_mc_" + cat["code"].lower(),
                           bank=1, cat_index=bank.mc_cats.index(cat), seed_index=bank.mc_sits.index(sit), k=k,
                           games=sorted(sit["games"]), flags=0, family=FAM_MC, graph=graph, outcomes=outs,
                           plan={"order": order}))
    return out


# ---- All of it ------------------------------------------------------------------------------------------------------


def generate(bank: Bank | None = None, k_total: int = K, mc: bool = True, mc_k: int = MC_K) -> list[Variant]:
    """Every variant, in pack order (LE seeds in bank order, then MC)."""
    bank = bank or Bank()
    MIX_CHANGES.clear()
    use = Usage()
    out: list[Variant] = []
    for seed in bank.seeds:
        out += le_variants(bank, seed, k_total, use)
    if mc:
        for sit in bank.mc_sits:
            if sit.get("outcomes_status") == "active":
                out += mc_variants(bank, sit, mc_k)
    for v in out:
        v.mood = mood_of(bank, v)
        title_case_labels(v.graph)
    return out


def title_case_labels(graph: dict) -> dict:
    """The owner (2026-11-15): every new event's choice labels in title case -- scripts/collection_lib's one switch,
    which the collection's own events take too (collection_check.graph_for_engine)."""
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import collection_lib
    return collection_lib.title_case_graph_labels(graph)


# The content filters (lead's list F01-F27, 2026-11-15): which outcomes each would drop before selection.  A Living
# Engine outcome is an archetype (by its words and effects); an MC outcome takes its category's subjects plus its
# own effects.  The pack's outcome records give every ending's archetype index (living-pack.md 2.4).
FILTERS = {"F01": "death_child", "F02": "pregnancy_loss", "F03": "death_any", "F04": "vanish", "F05": "bereavement",
           "F06": "injury_serious", "F07": "scars_burns", "F08": "illness_serious", "F09": "contagion",
           "F10": "birth_difficult", "F11": "distress", "F12": "hopelessness", "F13": "fear_eerie",
           "F14": "abuse_past", "F15": "history_harm", "F16": "bullying", "F17": "prejudice",
           "F18": "child_danger", "F19": "abandonment", "F20": "hunger", "F21": "disaster", "F22": "drowning",
           "F23": "fire", "F24": "animal_harm", "F25": "hunting", "F26": "creatures", "F27": "lasting_effects"}
ARCHETYPE_FILTERS = {
    "le_arc_bad_03": ["F20"],                     # a rushed choice wastes scarce supplies (food lost)
    "le_arc_mixed_03": ["F20"],                   # knowledge at the cost of time and materials (food spent)
    "le_arc_rare_01": ["F04", "F19"],             # the central villager leaves, fate unknown
    "le_arc_rare_02": ["F03", "F05", "F08"],      # a beloved elder dies after a long illness
    "le_arc_rare_03": ["F13"],                    # a rare creature glimpsed, nobody agrees what it was
}
MC_CATEGORY_FILTERS = {"DIS": ["F21"], "AFT": ["F15"], "LOS": ["F19", "F22"], "TRA": ["F11", "F14"],
                       "BEL": ["F16", "F17"], "ISL": []}
EFFECT_FILTERS = {"kill": ["F03"], "vanish": ["F04"], "die_unrecovered": ["F03"], "baby_lost": ["F02"],
                  "sick": ["F08"], "old_look": ["F27"]}


def mc_outcome_filters(bank: Bank, sit: dict, outcome: dict) -> list[str]:
    """An MC outcome's filters: its category's subjects and its effects'."""
    out = set(MC_CATEGORY_FILTERS[bank.mc_cat[sit["category"]]["code"]])
    for e in outcome["effects"]:
        out.update(EFFECT_FILTERS.get(e["do"], []))
    return sorted(out)


def outcome_categories(bank: Bank | None = None) -> dict[str, dict]:
    """Each Living Engine archetype's category for filtering before selection (owner answers 2026-11-15, Q29): its
    group, tags and the effects it carries ("do" names).  The pack's outcome records (living-pack.md 2.4) give the
    archetype index of every ending, so the engine can apply the same filter per variant (lv_excluded)."""
    bank = bank or Bank()
    return {a["id"]: {"index": bank.arc_index[a["id"]], "group": a["group"], "tags": list(a["tags"]),
                      "effects": sorted({e["do"] for e in a["effects"]}),
                      "filters": sorted(set(ARCHETYPE_FILTERS.get(a["id"], []))
                                        | {f for e in a["effects"] for f in EFFECT_FILTERS.get(e["do"], [])})}
            for a in bank.archetypes}


def mood_of(bank: Bank, v: Variant) -> int:
    """The MOODS index of a variant's seed: its category's mood."""
    if v.bank == 0:
        return MOODS.index(bank.cat[bank.seed[v.seed]["category"]]["mood"])
    return MOODS.index(bank.mc_cats[v.cat_index]["mood"])


def validate_variant(v: Variant) -> dict:
    g, problems = cg.validate(v.graph, scrolling=True)
    if problems:
        raise ValueError(f"{v.manifest_id} k={v.k}: " + "; ".join(problems[:6]))
    return g


def variant_tags(v: Variant, g: dict, bank: Bank | None = None) -> dict[str, list[str]]:
    """A variant's node tags for the content controls (src/vv_event_content.py): its words and effects, and each
    ending's archetype's filters (outcome_categories)."""
    import vv_event_content as content
    tags = {n: set(t) for n, t in content.tag_graph(g).items()}
    by_index = _arc_filters(bank)
    for name, _grp, arc in v.outcomes:
        if name in g["nodes"]:
            tags.setdefault(name, set()).update(by_index.get(arc, ()))
    return {n: sorted(t) for n, t in tags.items() if t}


_ARC_FILTERS: dict[int, list[str]] | None = None


def _arc_filters(bank: Bank | None = None) -> dict[int, list[str]]:
    global _ARC_FILTERS
    if _ARC_FILTERS is None:
        _ARC_FILTERS = {c["index"]: c["filters"] for c in outcome_categories(bank).values()}
    return _ARC_FILTERS


def compile_all(variants: list[Variant], bank: Bank | None = None) -> None:
    import vv_event_content as content
    for v in variants:
        g = validate_variant(v)
        g, _plan = content.inject(g, variant_tags(v, g, bank), {"speaks": content.speaking_roles(g)})
        # A new event (the Story DLL's cg_is_collection_event: a "collection" block in the header).
        g = dict(g, collection={"id": v.manifest_id, "source": "living_engine", "k": v.k})
        v.cieg = cg.compile_graph(g)
        order = list(g["nodes"])
        v.outcomes = [(name, grp, arc) for name, grp, arc in v.outcomes]
        v.plan["node_index"] = {name: order.index(name) for name, _g, _a in v.outcomes}


# ---- The pack (VLEP v1) ---------------------------------------------------------------------------------------------

_HEADER = struct.Struct("<4sHHIIBBHHHIIIIIIIIHHHH")
_SEED = struct.Struct("<HHHHBBHI")
_VARIANT = struct.Struct("<IIHBBHHBBHHH")
_OUTCOME = struct.Struct("<HBB")
assert _HEADER.size == 64 and _SEED.size == 16 and _VARIANT.size == 24 and _OUTCOME.size == 4


def pack(game: int, variants: list[Variant], bank: Bank | None = None) -> bytes:
    """The game's living.pak: every compiled variant valid in `game`, grouped by seed in the given order."""
    bank = bank or Bank()
    mine = [v for v in variants if game in v.games]
    seeds: list[str] = []
    by_seed: dict[str, list[Variant]] = {}
    for v in mine:
        if v.manifest_id not in by_seed:
            seeds.append(v.manifest_id)
            by_seed[v.manifest_id] = []
        by_seed[v.manifest_id].append(v)
    strings = bytearray()
    sidx: dict[str, int] = {}

    def s(text: str) -> int:
        if text not in sidx:
            sidx[text] = len(strings)
            strings.extend(text.encode("ascii") + b"\0")
        if sidx[text] > 0xFFFE:
            raise ValueError("the pack's strings outgrow 64 KB")
        return sidx[text]

    seed_recs = bytearray()
    var_recs = bytearray()
    out_recs = bytearray()
    blobs = bytearray()
    vi = oi = 0
    for si, sid in enumerate(seeds):
        vs = by_seed[sid]
        first = vs[0]
        seed_recs += _SEED.pack(s(sid), s(first.series), vi, len(vs), first.bank, first.cat_index, first.seed_index,
                                first.mood)
        for v in vs:
            if not v.cieg:
                raise ValueError(f"{sid} k={v.k} is not compiled")
            while len(blobs) % 4:
                blobs.append(0)
            mask = sum(1 << (g - 1) for g in v.games)
            outs = sorted(v.outcomes, key=lambda o: v.plan["node_index"][o[0]])
            var_recs += _VARIANT.pack(len(blobs), len(v.cieg), si, v.k, v.flags, v.role_a, v.role_b, v.lens, v.family,
                                      mask, oi, len(outs))
            for name, grp, arc in outs:
                out_recs += _OUTCOME.pack(v.plan["node_index"][name], grp, arc)
                oi += 1
            blobs += v.cieg
            vi += 1
    if len(seeds) > 2048 or vi > 0xFFFF or oi > 0xFFFF:
        raise ValueError("the pack outgrows its counts")
    off_seeds = _HEADER.size
    off_vars = off_seeds + len(seed_recs)
    off_outs = off_vars + len(var_recs)
    off_str = off_outs + len(out_recs)
    off_blobs = off_str + len(strings)
    off_blobs += (-off_blobs) % 4
    total = off_blobs + len(blobs)
    body = bytes(seed_recs + var_recs + out_recs + strings) + bytes(off_blobs - off_str - len(strings)) + bytes(blobs)

    def header(crc: int) -> bytes:
        return _HEADER.pack(b"VLEP", 1, _HEADER.size, total, crc, game, 0, len(seeds), vi, 0, off_seeds, off_vars,
                            off_outs, oi, off_str, len(strings), off_blobs, len(blobs), len(bank.roles),
                            len(bank.archetypes), len(bank.lenses), 0)
    crc = zlib.crc32(header(0) + body) & 0xFFFFFFFF
    data = header(crc) + body
    assert len(data) == total
    return data


def read_pack(data: bytes) -> dict:
    """The pack's tables (the engine's reading, for the tests and the native fixture)."""
    h = _HEADER.unpack_from(data, 0)
    (magic, version, hbytes, total, crc, game, _z, n_seeds, n_vars, _z2, off_seeds, off_vars, off_outs, n_outs, off_str,
     n_str, off_blobs, n_blobs, n_roles, n_arcs, n_lenses, _z3) = h
    if magic != b"VLEP" or version != 1 or hbytes != 64 or total != len(data):
        raise ValueError("not a VLEP v1 pack")
    if zlib.crc32(data[:12] + b"\0\0\0\0" + data[16:]) & 0xFFFFFFFF != crc:
        raise ValueError("crc")

    def string(off: int) -> str:
        end = data.index(b"\0", off_str + off)
        return data[off_str + off:end].decode("ascii")
    seeds = []
    for i in range(n_seeds):
        sid, ser, first, count, bank, cat, index, _ = _SEED.unpack_from(data, off_seeds + 16 * i)
        seeds.append({"id": string(sid), "series": string(ser), "first": first, "count": count, "bank": bank,
                      "category": cat, "index": index, "mood": _ & 0xFF})
    variants = []
    for i in range(n_vars):
        boff, bsize, si, k, flags, ra, rb, lens, fam, mask, of, oc = _VARIANT.unpack_from(data, off_vars + 24 * i)
        outs = [_OUTCOME.unpack_from(data, off_outs + 4 * j) for j in range(of, of + oc)]
        variants.append({"blob": data[off_blobs + boff:off_blobs + boff + bsize], "seed": si, "k": k, "flags": flags,
                         "role_a": ra, "role_b": rb, "lens": lens, "family": fam, "games": mask, "outcomes": outs})
    return {"game": game, "crc": crc, "seeds": seeds, "variants": variants, "roles": n_roles, "archetypes": n_arcs,
            "lenses": n_lenses}


# ---- The run-time twin: ordering a seed's variants (living-pack.md 4.2) --------------------------------------------

LV_TRIES = 12
LV_WEIGHT = 1000
RING = 64


@dataclass
class History:
    """The VLEH counts (living-pack.md 3)."""
    roles: int
    archetypes: int
    lenses: int
    variants: int
    ring: list[int] = field(default_factory=list)       # newest last
    pair: Counter = field(default_factory=Counter)
    lens: Counter = field(default_factory=Counter)
    family: Counter = field(default_factory=Counter)
    arc: Counter = field(default_factory=Counter)
    var: Counter = field(default_factory=Counter)

    def pair_key(self, a: int, b: int) -> int | None:
        if a == NONE16 or b == NONE16:
            return None
        return min(a, b) * self.roles + max(a, b)

    def uses(self, v: dict, vi: int) -> int:
        key = self.pair_key(v["role_a"], v["role_b"])
        return ((self.pair[key] if key is not None else 0) + (self.lens[v["lens"]] if v["lens"] != NONE8 else 0)
                + self.family[v["family"]] + self.var[vi])

    def armed(self, seed_index: int, v: dict, vi: int) -> None:
        self.ring = (self.ring + [seed_index])[-RING:]
        key = self.pair_key(v["role_a"], v["role_b"])
        if key is not None:
            self.pair[key] += 1
        if v["lens"] != NONE8:
            self.lens[v["lens"]] += 1
        self.family[v["family"]] += 1
        self.var[vi] += 1

    def finished(self, archetype: int) -> None:
        if archetype != NONE8:
            self.arc[archetype] += 1

    def recent(self, seed_count: int) -> set[int]:
        w = min(RING, seed_count // 3)
        return set(self.ring[-w:]) if w else set()

    def mood_weights(self, seed_moods: list[int]) -> list[int]:
        """Each mood's series weight in the rare roll's draw (living-pack.md 4.1a): the moods of the seeds in the
        ring are counted (`seed_moods[seed index]`); when they are not all equal, every mood with the fewest weighs
        MOOD_BOOST, the others 1."""
        count = [0] * len(MOODS)
        for si in self.ring:
            count[seed_moods[si]] += 1
        low = min(count)
        if low == max(count):
            return [1] * len(MOODS)
        return [MOOD_BOOST if c == low else 1 for c in count]


def lv_order(variants: list[dict], first: int, hist: History, random_below) -> list[int]:
    """The pack indexes of a seed's variants in the order the engine tries them (at most 12).  `variants` is the
    pack's variant list, the seed's are first .. first + count - 1 (the caller passes them as a slice's indexes);
    `random_below(n)` is the game's ce_random_below (no roll when n <= 1)."""
    left = list(range(first, first + len(variants)))
    weights = {vi: max(1, LV_WEIGHT // (1 + hist.uses(variants[vi - first], vi))) for vi in left}
    order = []
    while left and len(order) < LV_TRIES:
        total = sum(weights[vi] for vi in left)
        r = random_below(total) if total > 1 else 0
        pick = left[-1]
        for vi in left[:-1]:
            if r < weights[vi]:
                pick = vi
                break
            r -= weights[vi]
        order.append(pick)
        left.remove(pick)
    return order


# ---- Manifest rows --------------------------------------------------------------------------------------------------


def manifest_rows(game: int, variants: list[Variant], bank: Bank | None = None) -> list[dict]:
    """One row per seed the game's pack holds: id, title, games, weight, series, credit, description."""
    bank = bank or Bank()
    rows: dict[str, dict] = {}
    for v in variants:
        if game not in v.games:
            continue
        r = rows.get(v.manifest_id)
        if r is None:
            if v.bank == 0:
                seed = bank.seed[v.seed]
                text = plain(seed["text"])
                for src_words, name in seed.get("chief_words") or []:
                    text = text.replace(plain(src_words), CHIEF_WORDS[name]["3" if game == 3 else "*"], 1)
            else:
                text, words = mc_text(next(s for s in bank.mc_sits if s["id"] == v.seed)["text"])
                for name, vals in words.items():
                    text = text.replace("{@" + name + "}", vals["3" if game == 3 else "*"])
            r = rows[v.manifest_id] = {"id": v.manifest_id, "title": v.graph["title"], "games": set(),
                                       "weight": 1, "series": v.series, "credit": bank.credit, "description": text}
        r["games"] |= set(v.games)
    for r in rows.values():
        r["games"] = sorted(r["games"])
    return list(rows.values())


def build(bank: Bank | None = None, k_total: int = K) -> tuple[list[Variant], dict[int, bytes]]:
    """Generate, validate, compile and pack: (the variants, {game: living.pak})."""
    bank = bank or Bank()
    variants = generate(bank, k_total)
    compile_all(variants, bank)
    return variants, {game: pack(game, variants, bank) for game in GAMES}


# ---- The owner packet's table and the native agent's fixture --------------------------------------------------------

DOC = ROOT / "docs" / "event-collection" / "living-events.md"
DOC_BEGIN = "<!-- living-mixer: begin (written by python src/vv_living_mixer.py --write-docs) -->"
DOC_END = "<!-- living-mixer: end -->"


def changes_markdown(changes: list[dict] | None = None) -> str:
    """The block living-events.md section 7 holds: the sensitivity rules and every change variant 0 makes."""
    changes = MIX_CHANGES if changes is None else changes
    rows = ["### The rules the mixer adds (owner decision, 2026-11-15)", "",
            "The bank's rules above are extended with these; every variant obeys them (`scripts/living_check.py`).",
            "", "| Rule | What is never combined |", "|---|---|"]
    rows += [f"| {k} | {v} |" for k, v in SENSITIVITY_RULES.items()]
    rows += ["", "### Variant 0: the MIX examples as shipped, with every change", "",
             "Variant 0 of a seed is its MIX in the owner's words, with ONLY the piece that breaks a rule above "
             "swapped for the nearest compatible one, and the doubled-word grammar fix. A row marked \"alternative\" "
             "keeps both: the owner's original (Before) and the earlier replacement (After) are equal alternatives, "
             "and the game picks one at random (owner, 2026-11-15: archetypes are not bad). The MIX anchor test "
             "(`tests/test_living_fidelity.py`) reproduces each MIX from the source with exactly these changes.", "",
             "| MIX | What | Before | After | Why |", "|---|---|---|---|---|"]
    for c in sorted(changes, key=lambda c: (c["mix"], c["what"])):
        rows.append(f"| {c['mix']} | {c['what']} | {c['before']} | {c['after']} | {c['rule']} |")
    return DOC_BEGIN + "\n" + "\n".join(rows) + "\n" + DOC_END


def write_docs() -> None:
    text = DOC.read_text(encoding="utf-8")
    block = changes_markdown()
    if DOC_BEGIN in text:
        text = text[:text.index(DOC_BEGIN)] + block + text[text.index(DOC_END) + len(DOC_END):]
    else:
        anchor = "\n## 8. The MC bank"
        text = text.replace(anchor, "\n" + block + "\n" + anchor, 1)
    DOC.write_text(text, encoding="utf-8", newline="\n")


FIXTURE = ROOT / "tests" / "data" / "living_fixture"
FIXTURE_SEEDS = ("le_odd_08", "le_cel_01", "le_per_01", "le_art_05", "mc_tra_13", "mc_tra_08")
FIXTURE_K = 5                   # le_per_01 k = 4 is the first a village of four adults with no skills can cast


def fixture_files(variants: list[Variant], bank: Bank | None = None) -> dict[str, bytes]:
    """A small pack per game for the engine's tests: a few seeds (a MIX, the chief's words, a VV5-only variant, the
    VV5-only MIX-027, an MC health effect, the MC chief), their first FIXTURE_K variants; and each game's manifest
    rows for them."""
    bank = bank or Bank()
    chosen = [v for v in variants if v.seed in FIXTURE_SEEDS and v.k < FIXTURE_K]
    out = {}
    for game in GAMES:
        out[f"vv{game}.pak"] = pack(game, chosen, bank)
        rows = [f"{r['id']}\t{r['title']}\t{','.join(map(str, r['games']))}\t1\t{r['series']}\t{r['credit']}\t"
                f"{r['description']}\t\t" for r in manifest_rows(game, chosen, bank)]
        out[f"vv{game}_manifest.txt"] = ("\n".join(rows) + "\n").encode("ascii")
    return out


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    bank = Bank()
    variants, packs = build(bank)
    le = sum(1 for v in variants if v.bank == 0)
    mc = sum(1 for v in variants if v.bank == 1)
    print(f"variants: LE {le}, MC {mc}, MIX changes {len(MIX_CHANGES)}")
    for game, data in packs.items():
        p = read_pack(data)
        print(f"vv{game}: {len(p['seeds'])} seeds, {len(p['variants'])} variants, {len(data):,} bytes")
    if "--write-docs" in argv:
        write_docs()
        print(f"wrote {DOC.relative_to(ROOT)}")
    if "--write-fixture" in argv:
        FIXTURE.mkdir(parents=True, exist_ok=True)
        for name, data in fixture_files(variants, bank).items():
            (FIXTURE / name).write_bytes(data)
        print(f"wrote {FIXTURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
