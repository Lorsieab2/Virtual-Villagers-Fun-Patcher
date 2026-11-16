"""The Living Event Engine's mixer: the owner's bank (data/living_events/bank.json) composed into ordinary version 6
graphs at build time, and packed per game as "Island Event Collection\\living.pak" (docs/event-collection/
living-pack.md, VLEP v1).

* K variants per active seed (LE 120, MC 95; MJ is held), deterministic (each seed's own random stream, seeded from
  its id), with coverage balancing across the whole bank (roles, role pairs, archetypes, approaches, lenses).
* An LE variant: the seed sentence and the frame (two cast villagers, their personalities as pools PA / PB, PB never
  the same word as PA), 3 to 5 choices (the category's choice set, or approaches from different families), each a
  branch to a GOOD (20), an adverse MIXED or BAD (20) and a RARE (2) archetype page.  Archetype pages are shared
  nodes carrying their effects, with automatic lines when they have any.  Variant 0 of a seed with a MIX example is
  that MIX (the 15 MIX that break a compatibility rule get only the documented swaps, MIX_CHANGES).
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
# per choice (living-events.md Q7); the owner, 2026-11-15 ("ignore weights"): the rare outcome is as likely as the others
W_GOOD, W_ADVERSE, W_RARE = 20, 20, 20
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

# ---- The 15 MIX examples that break a compatibility rule (lead decision, 2026-11-14) -------------------------------
# Variant 0 reproduces the MIX but swaps ONLY the offending piece for the nearest compatible one (first in the list
# that every rule allows), and applies the doubled-word grammar fix ("a confident confident novice" -> "a confident
# novice").  Each change is listed in living-events.md section 7.
NEAREST_ARCHETYPE = {
    "le_arc_bad_03": ["le_arc_bad_09", "le_arc_bad_02", "le_arc_bad_07"],   # rushed choice -> idea abandoned
    "le_arc_bad_06": ["le_arc_bad_02", "le_arc_bad_09"],                    # confidence mistaken -> must admit uncertainty
    "le_arc_good_06": ["le_arc_good_02", "le_arc_good_07"],                 # misunderstanding corrected -> no proof
    "le_arc_good_10": ["le_arc_good_07", "le_arc_good_02"],                 # new song -> the person feels heard
    "le_arc_mixed_08": ["le_arc_mixed_04", "le_arc_mixed_02"],              # embarrassment -> awkward, disappointing
}
NEAREST_ROLE = {
    "le_role_teenager": ["le_role_adult_villager"],
    "le_role_child": ["le_role_adult_villager"],
}
NEAREST_ONE_GAME_ROLE = {"le_role_chief": "le_role_council_member"}
NEAREST_PERSONALITY = {
    "le_pers_forgetful": ["le_pers_thoughtful", "le_pers_methodical"],
    "le_pers_tired": ["le_pers_thoughtful", "le_pers_methodical"],
}


# ---- The owner's sensitivity rules (2026-11-14): no unfortunate implication in any combination or path -----------
# The bank's compat table (C1-C12, R1-R3, P1-P4) is extended here with the combinations of seed x role x personality x
# choice x archetype that would imply blame, stigma, mockery that hurts, or harm aimed at someone.  Every variant obeys
# them (scripts/living_check.py, tests/test_living_quality.py); a MIX that breaks one gets the smallest change, listed
# as a sensitivity edit (MIX_CHANGES, living-events.md section 7).
SENSITIVITY_RULES = {
    "S1": "A villager whom a harmful outcome of the variant can reach, and both villagers when a blame outcome is "
          "possible, never get a personality that can read as an insult or an age stereotype (insecure, tired, "
          "forgetful, blunt, superstitious): the bad outcome would read as that trait's fault.",
    "S2": "A mocking or comedic choice never leads to an outcome that hurts someone (an injury, a harm, someone "
          "excluded, leaving, a death, a friendship ending): the joke would read as the cause.",
    "S3": "A trial (an experiment, a new tool, magic, animal help, a small-scale or cautious trial) never leads to an "
          "injury or a death: never harm shown as inflicted by the trial.",
    "S4": "A confrontational choice (speaking candidly, a firm boundary, disagreeing, declining, the established "
          "custom, the chief deciding) never leads to someone leaving, a friendship ending, someone excluded or an "
          "injury: the choice would read as having driven someone away or hurt them.",
    "S5": "Belief and spirit seeds never call a villager superstitious (a stigma on believers).",
    "S6": "Asking an elder to explain the tradition never leads to an elder's death.",
    # Part 2 (owner, 2026-11-14): no power imbalance between minors and adults; child labour and cruelty to animals
    # never implied.
    "S7": "A romantic, secret-keeping or coercive frame (the adult-only seeds, a friend's secret, an elder demanding "
          "obedience, the choice to keep the matter private) casts adults only: both villagers 18 or older, never a "
          "child, a teenager or anyone younger than 18 in any role.",
    "S8": "An injury may land on a child or a teenager only at the rare tier, like any villager's rare harm (owner, "
          "2026-11-15: \"Allow it, rare\"); never from a comedic or a trial choice (S2, S3). The bank's only injury "
          "outcome (minor injury or exhaustion) is an adverse one (weight 20 of 60), so it never lands on a child or "
          "a teenager: a rare-tier injury line from the owner would be needed for one.",
    "S9": "Animal seeds never offer an experiment or a new tool on the creature (cruelty to animals would be implied).",
    # Owner world rule (2026-11-15): some villagers believe, others do not; whether gods or spirits exist stays
    # ambiguous; every belief and non-belief is valid and individual; nothing mocks, ranks or corrects a belief.
    "S10": "Belief and spirit seeds never take a mocking or comedic approach (a friendly contest, a joke, celebrating "
           "the result) and never end in an outcome that corrects or settles something (a misunderstanding gently "
           "corrected, confidence found mistaken): a belief would read as mocked or corrected.",
    # Owner rule (2026-11-15): villagers never murder or abuse; any other wrong act is acknowledged as wrong and has
    # fitting consequences, never justified, rewarded or laughed off; no bigotry or unjust hatred anywhere.
    "S11": "A seed whose situation is a wrong act (a prank that embarrasses someone, cheating alleged, a rule meant "
           "only for outsiders) never takes a mocking or comedic choice, never ends in a celebration or a light "
           "outcome, and never in one that keeps an unjust custom (customs coexisting, the tradition preserved); "
           "following the unjust custom is never offered, and where the owner's example offers it, its good outcome "
           "is one that acknowledges the people affected.",
    # Owner rules 15-18 (2026-11-15): appearance, body and disability are never a problem, a lesson or a punchline.
    "S12": "A seed about a villager's appearance or body (hair, clothes, a mask, a portrait) never takes a mocking or "
           "comedic choice and never ends in an outcome that blames or embarrasses the person: their looks would "
           "read as a problem or a punchline. The owner's own examples (variant 0) keep their words.",
    # Owner hard rules (2026-11-15) 12, 13 and 20: no victim-blaming; a random outcome never reads as deserved;
    # prejudice is never just another opinion.
    "S13": "A seed with someone wronged in it (a prank's target, a villager accused of cheating, the outsiders an "
           "old rule shuts out) never ends in an outcome that blames (wasted supplies, confidence mistaken for "
           "competence, an embarrassment): the one wronged would read as deserving it. A seed about a rule meant "
           "only for outsiders never offers a compromise with it, neutrality, letting households differ, leaving it "
           "unresolved or inviting several disagreeing voices, and never ends in a compromise that satisfies "
           "neither side: prejudice would read as one valid opinion.",
    "S14": "A grief, loss, illness or trauma seed never ends in an outcome that corrects or settles it (a "
           "misunderstanding gently corrected, confidence found mistaken) and never offers apologizing and repairing "
           "as its way through: a past harm would read as the person's fault, insignificant, or resolved by "
           "forgiveness (owner hard rule 27). Bad outcomes elsewhere stay what they are: not every one implies "
           "wrongdoing.",
    "S16": "Nothing serious is ever a joke: a seed of a serious category (Belief and Mystery, Governance and "
           "Fairness, Emotions and Identity; Rest, Health, and Care), a grief, loss, illness or trauma seed, or a "
           "seed about another community or culture (collective trauma may sit behind it; a culture is never shown "
           "as lesser) never takes a mocking or comedic choice; Emotions and Identity, and Rest, Health, and Care "
           "(care of the mind) never end in a light outcome. The owner's own examples keep their words.",
    "S17": "A seed about love, a couple, a family's view of a companion, or a villager who is alone (a love letter "
           "after years alone, a couple undecided about a child, a family that dislikes a companion, dining alone, "
           "loneliness) never takes a mocking choice, never an approach where someone else decides for them (the "
           "chief deciding, several voices, a trial), never an outcome that blames, and the couple's seed never ends "
           "in an unexpected birth: no choice obliges anyone to accept affection, marry or have children, and being "
           "single, childfree or alone is never lesser.",
    "S15": "No outcome shames anyone (owner hard rule 28): the archetypes \"The villagers discover that confidence "
           "was mistaken for competence.\" and \"A small success comes with an unexpected embarrassment.\" are never "
           "mixed into a variant. The owner's own examples (variant 0) that use them keep their words and are listed "
           "for the owner's review.",
}
PREJUDICE_SEEDS = {"le_gov_07"}                                     # S13
FALSE_EQUIVALENCE = {"le_app_relate_04", "le_app_relate_06", "le_app_withdraw_04", "le_app_withdraw_05",
                     "le_app_consult_04", "le_cs_gov_oth_d"}       # neutrality, compromise, households differ ...
SPLIT_THE_DIFFERENCE = {"le_arc_mixed_05"}                          # the compromise satisfies neither side
# Owner hard rule 27 (2026-11-15): no combination implies a past harm was the person's fault, insignificant, or
# resolved by forgiveness.  A grief, loss, illness or trauma seed (tagged somber or medical) never ends in an outcome
# that "corrects" or settles it, and never offers apologizing and repairing as its way through.
REPAIR_APPROACHES = {"le_app_relate_07"}                            # Apologize and repair the relationship
# Owner rules on relationships (2026-11-15): single, childfree and widowed villagers are never lesser or lonely by
# default; marriage and parenthood are never a goal everyone must reach; no choice obliges anyone to accept
# affection, marry or have children; relationships can end without blame; no family form is superior.
RELATIONSHIP_SEEDS = {"le_fam_05", "le_fam_06", "le_fam_07", "le_foo_07", "le_emo_04"}
BIRTH_OVERRIDES = {"le_fam_06": {"le_arc_rare_07"}}                # a couple undecided about a child: no birth page
# Owner hard rule 28 (2026-11-15, emphatic): no shaming.  The two archetype lines that judge a person's mistake or
# make it an embarrassment are never mixed in; the owner's own examples keep their words, flagged for review.
SHAMING_ARCHETYPES = {"le_arc_bad_06", "le_arc_mixed_08"}          # confidence mistaken for competence; embarrassment
KEPT_IN_OWNER_EXAMPLES = (None, "S12", "S15", "S16")              # the rules variant 0 does not apply
# Owner rule (2026-11-15): care of the mind (by healers, doctors, spiritual leaders or trusted villagers) is
# voluntary and private, no miracle cure, never mocked: Emotions and Identity, and Rest, Health, and Care, never end
# in a light outcome (a memorable day, a new song, an embarrassment).
MIND_CATEGORIES = {"le_cat_emo", "le_cat_res"}


def somber_seed(seed: dict) -> bool:
    return "somber" in seed["tags"] or "medical" in seed["tags"]
WRONG_ACT_SEEDS = {"le_cel_07", "le_gov_04", "le_gov_07"}          # S11
UNJUST_KEEP = {"le_arc_good_09", "le_arc_mixed_09"}                # customs coexist; the tradition preserved
ENDORSE_CHOICES = {"le_gov_07": {"le_cs_gov_oth_b"}}               # Follow the established custom
ACKNOWLEDGE = ("le_arc_good_07", "le_arc_good_01")                 # the person affected heard; dignity kept
APPEARANCE_SEEDS = {"le_per_01", "le_per_03", "le_per_04", "le_per_05", "le_per_07", "le_per_08", "le_cel_10",
                    "le_odd_07"}                                    # S12
ADULT_FRAME_SEEDS = {"le_fam_04", "le_gov_08"}      # plus every seed tagged adult_only
SECRET_CHOICES = {"le_app_withdraw_03"}              # Keep the matter private
ANIMAL_SEEDS_EXTRA = {"le_cel_09", "le_odd_01", "le_odd_04", "le_odd_09"}
ANIMAL_NO = {"le_app_act_01", "le_app_act_03"}       # Try a small experiment; Invent a new tool or technique
ADULT_AGE = 18
RISK_TAGS = ("insult_risk", "ageist_risk")
TRIAL_CHOICES = {"le_cs_art_per_a", "le_cs_foo_a", "le_cs_ani_d"}
CONFRONT = {"le_app_relate_02", "le_app_relate_03", "le_app_relate_05", "le_app_withdraw_02", "le_app_consult_05",
            "le_cs_gov_oth_b"}
HURT_TAGS = ("injury", "rare_harm", "vanish", "elder_death")
SENSITIVE_PERSONALITY = {   # the nearest personality with no insult or age risk (S1, S5)
    "le_pers_insecure": ["le_pers_cautious", "le_pers_private"],
    "le_pers_tired": ["le_pers_thoughtful", "le_pers_methodical"],
    "le_pers_forgetful": ["le_pers_thoughtful", "le_pers_methodical"],
    "le_pers_blunt": ["le_pers_stubborn", "le_pers_proud"],
    "le_pers_superstitious": ["le_pers_devout", "le_pers_cautious"],
}


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


def belief_corrected(bank: Bank, seed: dict, arc: str) -> bool:
    """S10: would this archetype read as correcting or settling the seed's belief?"""
    return belief_seed(seed) and "resolves" in bank.arc[arc]["tags"]


def seed_arc_rule(bank: Bank, seed: dict, arc: str) -> str | None:
    """S10-S12: the rule that keeps this archetype from this seed, None when none does."""
    if belief_corrected(bank, seed, arc):
        return "S10"
    tags = bank.arc[arc]["tags"]
    if seed["id"] in WRONG_ACT_SEEDS and ("light" in tags or arc in UNJUST_KEEP):
        return "S11"
    if seed["id"] in APPEARANCE_SEEDS and "blame" in tags:
        return "S12"
    if seed["id"] in WRONG_ACT_SEEDS and "blame" in tags:
        return "S13"
    if seed["id"] in PREJUDICE_SEEDS and arc in SPLIT_THE_DIFFERENCE:
        return "S13"
    if somber_seed(seed) and "resolves" in tags:
        return "S14"
    if arc in SHAMING_ARCHETYPES:
        return "S15"
    if seed["category"] in MIND_CATEGORIES and "light" in tags:
        return "S16"
    if seed["id"] in RELATIONSHIP_SEEDS and ("blame" in tags or arc in BIRTH_OVERRIDES.get(seed["id"], set())):
        return "S17"
    return None


def no_mocking(seed: dict, bank: Bank | None = None) -> bool:
    """S10-S12, S16: a seed that never takes a mocking or comedic choice (a serious category's too, given the bank)."""
    if bank is not None and bank.cat[seed["category"]].get("mood") == "serious":
        return True                                 # S16: nothing serious is ever a joke
    if somber_seed(seed) or "other_community" in seed["tags"]:
        return True                                 # S16: grief and trauma (also collective); another culture
    if seed["id"] in RELATIONSHIP_SEEDS:
        return True                                 # S17: love, family or solitude is never a punchline
    return belief_seed(seed) or seed["id"] in WRONG_ACT_SEEDS or seed["id"] in APPEARANCE_SEEDS


def endorse_ok(bank: Bank, seed: dict, kind: str, ident: str, arc: str) -> bool:
    """S11: after a choice that follows an unjust custom (only in the owner's example), a good outcome
    acknowledges the people affected."""
    if ident not in ENDORSE_CHOICES.get(seed["id"], set()) or bank.arc[arc]["group"] != "good":
        return True
    return arc in ACKNOWLEDGE


def archetype_possible(bank: Bank, seed: str, arc: str, a: str, b: str, owner_example: bool = False) -> bool:
    """owner_example: the owner's own example (variant 0), which keeps its words under KEPT_IN_OWNER_EXAMPLES."""
    if not bank.seed_allows(seed, "archetype", arc):
        return False
    rule = seed_arc_rule(bank, bank.seed[seed], arc)
    if rule and not (owner_example and rule in KEPT_IN_OWNER_EXAMPLES):
        return False
    if not (bank.role_allows_archetype(a, arc) and bank.role_allows_archetype(b, arc)):
        return False
    if "needs_elder" in bank.arc[arc]["tags"] and resolve_role(bank, "elder", a, b) is None:
        return False
    return cast_ok(bank, arc, a, b)


def minor_role(bank: Bank, rid: str) -> bool:
    """A role whose villager is always under 18 (a child, a teenager)."""
    return any(t in bank.role[rid]["tags"] for t in ("child", "teen"))


def cast_ok(bank: Bank, arc: str, a: str, b: str) -> bool:
    """S8: no injury or exhaustion on a child or a teenager."""
    for e in bank.arc[arc]["effects"]:
        if e["do"] == "health_change" and e.get("min", 0) < 0 and "role" in e:
            r = resolve_role(bank, e["role"], a, b)
            if r is not None and minor_role(bank, a if r == "first" else b):
                return False
    return True


def adult_seed(seed: dict) -> bool:
    return "adult_only" in seed["tags"] or seed["id"] in ADULT_FRAME_SEEDS


def adult_frame(seed: dict, choices) -> bool:
    """S7: a romantic, secret-keeping or coercive frame: both villagers 18 or older."""
    return adult_seed(seed) or any(ident in SECRET_CHOICES for _kind, ident in choices)


def animal_seed(seed: dict) -> bool:
    return seed["category"] == "le_cat_ani" or seed["id"] in ANIMAL_SEEDS_EXTRA


HARMFUL = ("kill", "vanish", "die_unrecovered", "baby_lost", "sick")


def harmful(e: dict) -> bool:
    do = e["do"]
    return (do in HARMFUL or (do == "health_change" and e.get("min", 0) < 0) or (do == "mood" and e.get("mood") == "bad")
            or (do == "skill" and (e.get("loss") or (e.get("min") or 0) < 0))
            or (do == "preference" and (e.get("list") == "dislikes" or "dislike" in e)))


def hurts(bank: Bank, arc: str) -> bool:
    a = bank.arc[arc]
    return (any(harmful(e) for e in a["effects"]) or any(t in a["tags"] for t in HURT_TAGS)
            or arc == "le_arc_bad_04")


def choice_classes(bank: Bank, kind: str, ident: str) -> set[str]:
    out = set()
    if kind == "approach":
        ap = bank.app[ident]
        if ap["kind"] == "comedic" or "mocking" in ap["tags"]:
            out.add("mocking")
        if ap["kind"] in ("experiment", "magic", "animal"):
            out.add("trial")
    else:
        tags = bank.choice[ident]["tags"]
        if "comedic" in tags or "mocking" in tags:
            out.add("mocking")
        if ident in TRIAL_CHOICES:
            out.add("trial")
    if ident in CONFRONT:
        out.add("confront")
    if ident == "le_app_consult_06":
        out.add("elder_ask")
    return out


def arc_ok_after(bank: Bank, kind: str, ident: str, arc: str) -> bool:
    """S2, S3, S4, S6: may this choice lead to this archetype?"""
    cls = choice_classes(bank, kind, ident)
    if "mocking" in cls and hurts(bank, arc):
        return False
    if "trial" in cls and arc in ("le_arc_bad_05", "le_arc_rare_02"):
        return False
    if "confront" in cls and arc in ("le_arc_rare_01", "le_arc_rare_04", "le_arc_bad_04", "le_arc_bad_05"):
        return False
    if "elder_ask" in cls and arc == "le_arc_rare_02":
        return False
    return True


def risky(bank: Bank, pid: str) -> bool:
    return any(t in bank.per[pid]["tags"] for t in RISK_TAGS)


def belief_seed(seed: dict) -> bool:
    return "belief" in seed["tags"] or "supernatural" in seed["tags"]


def sensitive_slots(bank: Bank, arcs, a: str, b: str, games: list[int]) -> set[str]:
    """S1: the frame slots ('first', 'second') that may not take a risky personality."""
    arcs = [x for x in arcs if x]
    if any("blame" in bank.arc[x]["tags"] for x in arcs):
        return {"first", "second"}
    out = set()
    for x in arcs:
        for e in archetype_effects(bank, x, a, b, games):
            if harmful(e) and e.get("role") in ("first", "second"):
                out.add(e["role"])
    return out


def personality_ok(bank: Bank, seed: dict, role: str, pid: str, sensitive: bool) -> bool:
    if not bank.role_allows_personality(role, pid):
        return False
    if sensitive and risky(bank, pid):
        return False
    if belief_seed(seed) and pid == "le_pers_superstitious":
        return False
    return True


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
    personality word) or "pool" (the PA / PB pool).  choices: (kind, id).  outcomes[i]: (good, adverse, rare)."""
    text, words = seed_text(bank, seed)
    pools = {}
    slots = sensitive_slots(bank, [x for trio in outcomes for x in trio], a, b, games)
    if pers_a == "pool":
        pools["PA"] = {"items": [personality_item(bank, p["id"]) for p in bank.pers
                                 if personality_ok(bank, seed, a, p["id"], "first" in slots)]}
    if pers_b == "pool":
        pools["PB"] = {"items": [personality_item(bank, p["id"]) for p in bank.pers
                                 if personality_ok(bank, seed, b, p["id"], "second" in slots)],
                       **({"distinct_from": ["PA"]} if "PA" in pools else {})}
    part_a = frame_part(bank, a, None if pers_a is None else (pers_a if pers_a != "pool" else None),
                        "PA" if pers_a == "pool" else None)
    part_b = frame_part(bank, b, None if pers_b is None else (pers_b if pers_b != "pool" else None),
                        "PB" if pers_b == "pool" else None)
    setup = f"{text} (first), {part_a}, and (second), {part_b}, {FRAME_TAIL}"
    nodes: dict = {}
    q_choices = []
    used_arcs: list[str] = []
    for i, ((kind, ident), (good, adverse, rare)) in enumerate(zip(choices, outcomes)):
        label, w = label_text(bank, kind, ident)
        words.update(w)
        q_choices.append({"label": label, "next": f"c{i + 1}"})
        kids = [{"next": "o_" + good[7:], "weight": W_GOOD}, {"next": "o_" + adverse[7:], "weight": W_ADVERSE}]
        if rare:
            kids.append({"next": "o_" + rare[7:], "weight": W_RARE})
        for x in (good, adverse, rare):
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
                new = next(p for p in NEAREST_PERSONALITY[item] if bank.role_allows_personality(left_role, p))
                changes.append({"mix": mix["code"], "what": f"{slot} villager's personality", "before": ptext,
                                "after": bank.per[new]["text"], "rule": conflict})
                if slot == "first":
                    pa = new
                else:
                    pb = new
        else:                                                # seed x archetype, role x archetype: swap the outcome
            for i, pair in enumerate(outs):
                for j, arc in enumerate(pair):
                    if arc != item:
                        continue
                    new = next(x for x in NEAREST_ARCHETYPE[item] if archetype_possible(bank, seed, x, a, b))
                    pair[j] = new
                    changes.append({"mix": mix["code"], "what": f"choice {'ABCD'[i]} outcome {'12'[j]}",
                                    "before": bank.arc[item]["text"], "after": bank.arc[new]["text"],
                                    "rule": conflict})
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
    # The owner's sensitivity rules (S1-S6): the smallest change, each a sensitivity edit for the owner's review.
    sdict = bank.seed[seed]
    games = variant_games(bank, sdict, a, b)
    for i, ((kind, ident), pair) in enumerate(zip(choices, outs)):
        for j, arc in enumerate(pair):
            # S12 and S15 keep the owner's own examples as written (keep owner text by default; flagged for review).
            if arc_ok_after(bank, kind, ident, arc) and cast_ok(bank, arc, a, b) \
                    and seed_arc_rule(bank, sdict, arc) in KEPT_IN_OWNER_EXAMPLES \
                    and endorse_ok(bank, sdict, kind, ident, arc):
                continue
            group = ("good",) if bank.arc[arc]["group"] == "good" else ("mixed", "bad")
            same = [x["id"] for x in bank.archetypes if x["group"] in group]
            cands = NEAREST_ARCHETYPE.get(arc, []) + sorted(same, key=lambda x: (abs(bank.arc_index[x] - bank.arc_index[arc]),
                                                                                  bank.arc_index[x]))
            if not endorse_ok(bank, sdict, kind, ident, arc):
                cands = list(ACKNOWLEDGE) + cands
            new = next(x for x in cands if archetype_possible(bank, seed, x, a, b) and arc_ok_after(bank, kind, ident, x)
                       and not hurts(bank, x) and "blame" not in bank.arc[x]["tags"]
                       and endorse_ok(bank, sdict, kind, ident, x))
            pair[j] = new
            changes.append({"mix": mix["code"], "what": f"choice {'ABCD'[i]} outcome {'12'[j]} (sensitivity edit)",
                            "before": bank.arc[arc]["text"], "after": bank.arc[new]["text"],
                            "rule": seed_arc_rule(bank, sdict, arc)
                            or ("S11" if not endorse_ok(bank, sdict, kind, ident, arc) else None)
                            or next((r for r, c in (("S2", "mocking"), ("S3", "trial"), ("S4", "confront"),
                                                      ("S6", "elder_ask"))
                                       if c in choice_classes(bank, kind, ident)
                                       and not arc_ok_after(bank, kind, ident, arc)), "S8")})
    slots = sensitive_slots(bank, [x for p in outs for x in p], a, b, games)
    for slot in ("first", "second"):
        cur, role = (pa, a) if slot == "first" else (pb, b)
        if cur is None or personality_ok(bank, sdict, role, cur, slot in slots):
            continue
        rule = "S5" if belief_seed(sdict) and cur == "le_pers_superstitious" and not (slot in slots and risky(bank, cur)) \
            else "S1"
        new = next(p for p in SENSITIVE_PERSONALITY[cur] if personality_ok(bank, sdict, role, p, slot in slots)
                   and p != (pb if slot == "first" else pa))
        changes.append({"mix": mix["code"], "what": f"{slot} villager's personality (sensitivity edit)",
                        "before": bank.per[cur]["text"], "after": bank.per[new]["text"], "rule": rule})
        if slot == "first":
            pa = new
        else:
            pb = new
    return {"a": a, "b": b, "pa": pa, "pb": pb, "choices": choices, "outs": outs}, changes


MIX_CHANGES: list[dict] = []        # filled by generate(): every change the 15 conflicting MIX get


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
    out = [("choice", c) for c in cs["choices"] if bank.seed_allows(seed["id"], "choice", c)
           and not (no_mocking(seed, bank) and "mocking" in choice_classes(bank, "choice", c))     # S10-S12, S16
           and c not in ENDORSE_CHOICES.get(seed["id"], set())                                      # S11
           and not (seed["id"] in PREJUDICE_SEEDS and c in FALSE_EQUIVALENCE)]                      # S13
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
    """The bank's seed x approach exclusions, S7 (no secret-keeping with a child or a teenager) and S9."""
    if not bank.seed_allows(seed["id"], "approach", ident):
        return False
    if ident in SECRET_CHOICES and (minor_role(bank, a) or minor_role(bank, b)):
        return False
    if ident in ANIMAL_NO and animal_seed(seed):
        return False
    if no_mocking(seed, bank) and "mocking" in choice_classes(bank, "approach", ident):
        return False                                # S10-S12
    if seed["id"] in PREJUDICE_SEEDS and ident in FALSE_EQUIVALENCE:
        return False                                # S13
    if somber_seed(seed) and ident in REPAIR_APPROACHES:
        return False                                # S14
    if seed["id"] in RELATIONSHIP_SEEDS and "consent_risk" in bank.app[ident]["tags"]:
        return False                                # S17: nobody else decides who they love or whether to have a child
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
                  rng: random.Random, fixed: list[list[str]] | None = None,
                  avoid: tuple = (frozenset(), ())) -> list[tuple[str, str, str]]:
    """avoid = (the frame slots holding a fixed risky personality, the games): no rare may harm them (S1)."""
    ok = [x["id"] for x in bank.archetypes if archetype_possible(bank, seed, x["id"], a, b)]
    goods = [x for x in ok if bank.arc[x]["group"] == "good"]
    adverse = [x for x in ok if bank.arc[x]["group"] in ("mixed", "bad")]
    rares = [x for x in ok if bank.arc[x]["group"] == "rare"]
    out = []
    in_variant: Counter = Counter()

    def score(x):
        return use[("arc", x)] + 3 * local[("arc", x)] + 50 * in_variant[x]

    for i, (kind, ident) in enumerate(choices):
        after = [x for x in ok if arc_ok_after(bank, kind, ident, x)]
        if fixed is not None:
            g, d = fixed[i]
        else:
            g = _pick([x for x in goods if x in after], score, rng)
            in_variant[g] += 1
            d = _pick([x for x in adverse if x in after], score, rng)
            in_variant[d] += 1
        r = _pick([x for x in rares if x in after and not any(
            harmful(e) and e.get("role") in avoid[0] for e in archetype_effects(bank, x, a, b, list(avoid[1])))],
            score, rng)
        if r:
            in_variant[r] += 1
        out.append((g, d, r))
    if fixed is None and all(bank.arc[g]["effects"] and bank.arc[d]["effects"] for g, d, _r in out):
        # At least one path with no effect (quality D): the last choice's adverse page becomes an effect-free one.
        kind, ident = choices[-1]
        free = [x for x in adverse if not bank.arc[x]["effects"] and arc_ok_after(bank, kind, ident, x)]
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
            outs = pick_outcomes(bank, seed["id"], a, b, plan["choices"], use, local, rng, fixed=plan["outs"],
                                 avoid=({sl for sl, p in (("first", plan["pa"]), ("second", plan["pb"]))
                                         if p and risky(bank, p)}, games))
            graph, onodes = compose_le(bank, seed, a, b, plan["pa"], plan["pb"], plan["choices"], outs, games)
            v = Variant(k=k, games=games, flags=FLAG_MIX | FLAG_SET, role_a=bank.role_index[a],
                        role_b=bank.role_index[b], lens=NONE8, family=FAM_CHOICE_SET, graph=graph, outcomes=onodes,
                        plan={"roles": [a, b], "personalities": [plan["pa"], plan["pb"]], "choices": plan["choices"],
                              "outcomes": outs, "mix": mix["id"], "changes": changes}, **base)
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
            kids.append({"next": name, "weight": 1})   # "ignore weights" (owner, 2026-11-15): all outcomes equal
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
    return out


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


def compile_all(variants: list[Variant]) -> None:
    for v in variants:
        g = validate_variant(v)
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
    compile_all(variants)
    return variants, {game: pack(game, variants, bank) for game in GAMES}


# ---- The owner packet's table and the native agent's fixture --------------------------------------------------------

DOC = ROOT / "docs" / "event-collection" / "living-events.md"
DOC_BEGIN = "<!-- living-mixer: begin (written by python src/vv_living_mixer.py --write-docs) -->"
DOC_END = "<!-- living-mixer: end -->"


def changes_markdown(changes: list[dict] | None = None) -> str:
    """The block living-events.md section 7 holds: the sensitivity rules and every change variant 0 makes."""
    changes = MIX_CHANGES if changes is None else changes
    rows = ["### The sensitivity rules the mixer adds (owner, 2026-11-14)", "",
            "The bank's rules above are extended with these; every variant obeys them (`scripts/living_check.py`).",
            "", "| Rule | What is never combined |", "|---|---|"]
    rows += [f"| {k} | {v} |" for k, v in SENSITIVITY_RULES.items()]
    rows += ["", "### Variant 0: the MIX examples as shipped, with every change", "",
             "Lead decision (2026-11-14): variant 0 of a seed is its MIX, with ONLY the offending piece swapped for "
             "the nearest compatible one, and the doubled-word grammar fix. Changes marked \"sensitivity edit\" follow "
             "the owner's content rules (S1-S9) and are listed for the owner's review. The MIX anchor test "
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
FIXTURE_SEEDS = ("le_odd_09", "le_cel_01", "le_per_01", "le_art_05", "mc_tra_13", "mc_tra_08")
FIXTURE_K = 3


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
