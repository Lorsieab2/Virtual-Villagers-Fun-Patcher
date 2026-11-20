"""Build data/living_events/bank.json from the frozen Living Event Engine source (agent 1, v1.35.97).

Usage: python scripts/living_bank_build.py   (rewrites the bank from the frozen source and the tag tables here)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SRC_REL = "docs/more-island-events/Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt"
LINES = (ROOT / SRC_REL).read_text(encoding="utf-8").split("\n")


def L(n):
    return LINES[n - 1]


def src(n):
    return f"L{n}"


def find(text, lo, hi):
    hits = [n for n in range(lo, hi + 1) if text in L(n)]
    assert len(hits) == 1, (text, hits)
    return hits[0]


ALL = [1, 2, 3, 4, 5]

# ---------------------------------------------------------------- seeds
CATS = []          # (code, heading, line)
SEEDS = []
cat = None
for n in range(23836, 23979):
    s = L(n)
    m = re.match(r"^  ([A-Z]{3})-(\d\d): (.+)$", s)
    if m:
        SEEDS.append({"code": f"{m[1]}-{m[2]}", "cat": m[1], "text": m[3], "line": n})
        if cat[0] is None:
            cat[0] = m[1]
        continue
    if s.strip() and s == s.upper() and not s.startswith(" "):
        cat = [None, s, n]
        CATS.append(cat)
assert len(SEEDS) == 120 and len(CATS) == 12

# --- seed tags (see docs/event-collection/living-events.md, "Seed tags")
CAT_IDS = {c[0] for c in CATS}
def ids(*codes):
    return set(codes)

PERSONAL = {s["code"] for s in SEEDS if s["cat"] in ("PER", "FAM", "EMO", "RES")} | ids(
    "CEL-07", "CEL-10", "GOV-05", "GOV-08", "GOV-10", "OTH-03", "OTH-05", "OTH-08", "FOO-03", "FOO-06", "FOO-07",
    "ODD-03", "ODD-07")
PLAYFUL = {s["code"] for s in SEEDS if s["cat"] in ("CEL", "ODD", "FOO")} | ids("ANI-02")
CELEBRATION = {s["code"] for s in SEEDS if s["cat"] == "CEL"} | ids("PER-05", "PER-10", "OTH-06")
SUPERNATURAL = ids("BEL-01", "BEL-02", "BEL-04", "BEL-05", "BEL-06", "BEL-07", "BEL-09")
BELIEF = {s["code"] for s in SEEDS if s["cat"] == "BEL"} | ids("ART-06")
MEDICAL = ids("ART-07", "RES-01", "RES-02", "RES-03", "RES-04", "RES-05", "RES-06", "RES-07", "RES-08", "RES-09")
SOMBER = ids("FAM-02", "EMO-04", "EMO-10", "RES-02", "RES-09", "RES-10", "BEL-06", "GOV-10")
CHILD_SUBJECT = ids("FAM-01", "FAM-03", "ANI-06", "CEL-04", "FOO-03", "ODD-02", "RES-04", "EMO-03", "BEL-02",
                    "ART-06", "OTH-10")
ADULT_ONLY = ids("FAM-05", "FAM-06", "FAM-07", "CEL-10")
OTHER_COMMUNITY = {s["code"] for s in SEEDS if s["cat"] == "OTH"}
ELDER_DEATH_OK = ids("ART-03", "ART-09")
VV5_ONLY = ids("PER-05")
CHIEF = {  # substring of the seed -> game word (the word's VV3 value is the owner's own text)
    "CEL-01": [["The chief", "Chief"]],
    "GOV-01": [["The chief", "Chief"]],
    "GOV-09": [["the chief’s", "chiefs_possessive"]],
    "ODD-01": [["the chief’s", "chiefs_possessive"]],
    "EMO-07": [["A chief", "A_chief"]],
}
SUBJECT = {  # who the seed is about (text only, never cast: the frame's two villagers are the ones who disagree)
    "PER": "a villager", "FAM": "a family member", "CEL": "a villager", "ART": "a craftsperson or scholar",
    "ANI": "an animal or plant", "BEL": "a villager", "GOV": "a villager", "OTH": "a visitor or neighbour",
    "FOO": "a villager", "EMO": "a villager", "RES": "a villager", "ODD": "a villager or animal",
}
SEED_EFFECTS = {  # proposals, held until the owner answers Q6
    "PER-01": [{"do": "appearance", "role": "subject", "what": "hair_colour", "status": "proposed"}],
    "ART-01": [{"do": "tech", "size": "small", "scaled": True, "status": "proposed"}],
    "ART-10": [{"do": "tech", "size": "small", "scaled": True, "status": "proposed"}],
    "FOO-05": [{"do": "food", "size": "small", "scaled": True, "status": "proposed"}],
    "FOO-09": [{"do": "food", "size": "small", "scaled": True, "status": "proposed"}],
}

def seed_id(code):
    return "le_" + code.lower().replace("-", "_")

seeds_out = []
for s in SEEDS:
    c = s["code"]
    tags = sorted(t for t, members in (
        ("personal", PERSONAL), ("playful", PLAYFUL), ("celebration", CELEBRATION),
        ("supernatural", SUPERNATURAL), ("belief", BELIEF), ("medical", MEDICAL), ("somber", SOMBER),
        ("child_subject", CHILD_SUBJECT), ("adult_only", ADULT_ONLY), ("other_community", OTHER_COMMUNITY),
        ("elder_death_ok", ELDER_DEATH_OK), ("chief", set(CHIEF))) if c in members)
    seeds_out.append({
        "id": seed_id(c), "code": c, "category": "le_cat_" + s["cat"].lower(),
        "text": s["text"], "src": src(s["line"]),
        "games": [5] if c in VV5_ONLY else ALL,
        "tags": tags,
        "chief_words": CHIEF.get(c, []),
        "subject_cast": SUBJECT[s["cat"]],
        "primary_any_of": None, "secondary_any_of": None,
        "seed_effects": SEED_EFFECTS.get(c, []),
        "vv5_only": c in VV5_ONLY,
        "guardians": "isolan_communities" if c in OTHER_COMMUNITY else None,
        "consent_choice_required": c in MEDICAL,
    })

def title_case(h):
    small = {"and", "or", "of", "the", "a", "an", "in", "on", "at", "to", "for"}
    words = h.lower().split(" ")
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))

# The owner's Global Editorial Override (Isola_Complete_Anthology.txt, item 10): roughly one third warm / funny /
# ordinary, one third curious / social / mixed, one third serious / solemn / mysterious.  Each category's mood; the
# engine biases the living draw toward the mood its history has seen least (living-pack.md 4.1a).
MOODS = ("warm", "social", "serious")
LE_MOOD = {"PER": "warm", "FAM": "social", "CEL": "warm", "ART": "social", "ANI": "social", "BEL": "serious",
           "GOV": "serious", "OTH": "social", "FOO": "warm", "EMO": "serious", "RES": "serious", "ODD": "warm"}
MC_MOOD = {"ISL": "social", "DIS": "serious", "AFT": "serious", "LOS": "serious", "TRA": "serious", "BEL": "social"}

categories_out = [{"id": "le_cat_" + c[0].lower(), "code": c[0], "heading": c[1], "src": src(c[2]),
                   "title": title_case(c[1]), "mood": LE_MOOD[c[0]]} for c in CATS]

# ---------------------------------------------------------------- roles, personalities, lenses
ROLE_LINE, PERS_LINE, LENS_LINE = 23980, 23981, 23824
role_items = L(ROLE_LINE).split(": ", 1)[1].split("; ")
pers_items = L(PERS_LINE).split(": ", 1)[1].split("; ")
# The list ends at its sentence's full stop: "... humor, or uncertainty. A single seed can support several lenses."
lens_items = L(LENS_LINE).split(": ", 1)[1].split(". ", 1)[0].replace("or uncertainty", "uncertainty").split(", ")
assert len(role_items) == 30 and len(pers_items) == 24 and len(lens_items) == 15, (len(role_items), len(pers_items), len(lens_items))

def adult(**kw):
    d = {"kind": "villager", "min_age": 14}
    d.update(kw)
    return d

def skill(*names, mn=1, pick="random"):
    return {"names": list(names), "min": mn, "pick": pick}

MASTER = 50   # "master" casting floor; see living-events.md (unclear item U2)
CAST = {
    "chief": {"kind": "villager", "min_age": 0, "special": "tribal_chief"},
    "council member": adult(min_age=18),
    "master healer": adult(skill=skill("Healing", mn=MASTER, pick="highest")),
    "master builder": adult(skill=skill("Building", mn=MASTER, pick="highest")),
    "master scientist": adult(skill=skill("Research", mn=MASTER, pick="highest")),
    "master farmer": adult(skill=skill("Farming", mn=MASTER, pick="highest")),
    "master fisher": adult(min_age=18),
    "master parent": adult(skill=skill("Parenting", mn=MASTER, pick="highest")),
    "spiritual elder": adult(min_age=55),
    "Nature practitioner": adult(skill=skill("Devotion", mn=1)),
    "Magic practitioner": adult(skill=skill("Devotion", mn=1)),
    "apprentice": adult(max_age=24),
    "rookie": adult(max_age=24),
    "child": {"kind": "villager", "min_age": 3, "max_age": 13},
    "teenager": {"kind": "villager", "min_age": 14, "max_age": 17},
    "adult villager": adult(min_age=18, max_age=54),
    "elderly villager": adult(min_age=55),
    "visiting Isolan": {"kind": "stranger", "sex": "random"},
    "skeptical observer": adult(),
    "shy craftsperson": adult(skill=skill("Building", mn=1)),
    "confident novice": adult(max_age=24),
    "caretaker": adult(skill=skill("Parenting", "Healing", mn=1)),
    "storyteller": adult(),
    "musician": adult(),
    "weaver": adult(),
    "cook": adult(),
    "gardener": adult(skill=skill("Farming", mn=1)),
    "fisher": adult(),
    "relative": {"kind": "villager", "min_age": 3},
    "friend": {"kind": "villager", "min_age": 3},
}
ROLE_GAMES = {"chief": [3], "Nature practitioner": [5], "Magic practitioner": [5]}
ROLE_TAGS = {
    "child": ["child", "vulnerable"], "teenager": ["teen", "vulnerable"], "elderly villager": ["elder", "vulnerable"],
    "spiritual elder": ["elder"], "apprentice": ["novice"], "rookie": ["novice"], "confident novice": ["novice"],
    "chief": ["leader"], "council member": ["leader"],
    "master healer": ["master"], "master builder": ["master"], "master scientist": ["master"],
    "master farmer": ["master"], "master fisher": ["master"], "master parent": ["master"],
    "visiting Isolan": ["stranger"],
}
ROLE_NOTES = {
    "master fisher": "no game has a fishing skill: cast as any adult (18+)",
    "spiritual elder": "age 55+; Devotion exists only in VV5, so no skill requirement",
    "Nature practitioner": "VV5 only (Devotion); open question Q5",
    "Magic practitioner": "VV5 only (Devotion); open question Q5",
    "chief": "the VV3 Tribal Chief only; open question Q5",
    "visiting Isolan": "a stranger (no confirmed outsiders arrive; another Isolan village)",
    "weaver": "no weaving skill in any game: any adult",
    "cook": "no cooking skill in any game: any adult",
    "musician": "no music skill: any adult", "storyteller": "no storytelling skill: any adult",
}

def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

roles_out = []
for item in role_items:
    art, word = item.split(" ", 1)
    assert art in ("a", "an")
    roles_out.append({"id": "le_role_" + slug(word), "text": item, "src": src(ROLE_LINE), "article": art,
                      "word": word, "cast": CAST[word], "games": ROLE_GAMES.get(word, ALL),
                      "tags": ROLE_TAGS.get(word, []), "note": ROLE_NOTES.get(word, "")})
assert len(CAST) == 30

PERS_TAGS = {"forgetful": ["ageist_risk", "insult_risk"], "tired": ["ageist_risk", "insult_risk"],
             "insecure": ["insult_risk"], "superstitious": ["insult_risk"], "blunt": ["insult_risk"]}
pers_out = [{"id": "le_pers_" + p, "text": p, "src": src(PERS_LINE), "article": "an" if p[0] in "aeiou" else "a",
             "tags": PERS_TAGS.get(p, [])} for p in pers_items]
lens_out = [{"id": "le_lens_" + l, "text": l, "src": src(LENS_LINE)} for l in lens_items]

# ---------------------------------------------------------------- approaches
FAM_LINES = {"CONSULT": 23983, "ACT": 23992, "RELATE": 24002, "WITHDRAW": 24012, "PLAY": 24020}
APP_KIND = {  # kind: what the approach is, used by the filters
    "Try a small experiment": "experiment", "Invent a new tool or technique": "experiment",
    "Use animal assistance with appropriate care": "animal", "Try a magical method if available": "magic",
    "Hold a ritual or prayer if desired": "prayer", "Ask the chief to decide": "authority",
    "Seek the affected person’s wishes": "consent", "Let the other person choose": "consent",
    "Turn the disagreement into a friendly contest": "comedic", "Make a joke if everyone is comfortable": "comedic",
    "Celebrate the unexpected result": "comedic", "Invite the villagers to improvise": "play",
    "Try the idea for one day only": "play", "Invite several disagreeing voices": "public",
}
APP_TAGS = {
    "Try a small experiment": ["consent_risk"], "Try a magical method if available": ["consent_risk"],
    "Use animal assistance with appropriate care": ["consent_risk"], "Ask the chief to decide": ["consent_risk", "chief"],
    "Invite several disagreeing voices": ["consent_risk"],
    "Turn the disagreement into a friendly contest": ["mocking"], "Make a joke if everyone is comfortable": ["mocking"],
    "Celebrate the unexpected result": ["mocking"],
}
apps_out = []
for fam, start in FAM_LINES.items():
    n, k = start + 1, 0
    while L(n).startswith(" - "):
        k += 1
        t = L(n)[3:]
        apps_out.append({"id": f"le_app_{fam.lower()}_{k:02d}", "family": fam.lower(), "text": t, "src": src(n),
                         "kind": APP_KIND.get(t, "talk"), "tags": APP_TAGS.get(t, [])})
        n += 1
assert len(apps_out) == 34

# ---------------------------------------------------------------- archetypes
ARC_LINES = {"GOOD": 24027, "MIXED": 24039, "BAD": 24051, "RARE": 24063}
def eff(**kw):
    return kw
ARC_EFFECTS = {  # role "first"/"second" are the frame's two villagers; "junior" = the novice-tagged one, else first
    "A novice gains experience while a master gains perspective.":
        [eff(do="skill", role="junior", skills="any", size="normal")],
    "The participants learn something useful and keep their dignity.":
        [eff(do="skill", role="first", skills="any", size="small"), eff(do="skill", role="second", skills="any", size="small")],
    "The choice strengthens an unexpected friendship.":
        [eff(do="mood", role="first", mood="good"), eff(do="mood", role="second", mood="good")],
    "The villagers discover a practical improvement worth remembering.": [eff(do="tech", size="small", scaled=True)],
    "The person most affected feels heard and makes their own choice.": [eff(do="mood", role="first", mood="good")],
    "The village enjoys a memorable day without any larger crisis.": [eff(do="celebrate", who="all")],
    "The village gains knowledge at the cost of time and materials.":
        [eff(do="tech", size="small", scaled=True), eff(do="food", size="small", scaled=True, loss=True)],
    "A small success comes with an unexpected embarrassment.": [eff(do="mood", role="first", mood="bad")],
    "A rushed choice wastes scarce supplies.": [eff(do="food", size="small", scaled=True, loss=True)],
    "Someone feels excluded and withdraws from the gathering.": [eff(do="mood", role="second", mood="bad")],
    "The effort causes minor injury or exhaustion, requiring rest and care.":
        [eff(do="health_change", role="first", min=-20, max=-10)],
    "The central villager leaves for a time and their fate remains unknown.": [eff(do="vanish", role="first")],
    "A beloved elder dies after a long illness, leaving conflicting memories and affection.":
        [eff(do="kill", role="elder", cause="unknown")],
    "A fragile friendship ends despite sincere attempts to mend it.": [eff(do="mood", role="second", mood="bad")],
    "A chance observation preserves a piece of knowledge thought lost.": [eff(do="tech", size="small", scaled=True)],
}
ARC_TAGS = {
    "The village enjoys a memorable day without any larger crisis.": ["light"],
    "The result inspires a new song, pattern, or story.": ["light"],
    "A small success comes with an unexpected embarrassment.": ["light", "blame"],
    "A rushed choice wastes scarce supplies.": ["blame"],
    "The villagers discover that confidence was mistaken for competence.": ["blame", "resolves"],
    "A long-held misunderstanding is gently corrected.": ["resolves"],
    "The effort causes minor injury or exhaustion, requiring rest and care.": ["injury"],
    "The central villager leaves for a time and their fate remains unknown.": ["rare_harm", "vanish"],
    "A beloved elder dies after a long illness, leaving conflicting memories and affection.":
        ["rare_harm", "elder_death", "needs_elder"],
    "A fragile friendship ends despite sincere attempts to mend it.": ["rare_harm"],
    "An important heirloom is lost and cannot be recovered.": ["rare_harm"],
    "An unexpected birth or reunion changes the day’s priorities.": ["birth"],
}
HARM = ("kill", "vanish", "die_unrecovered", "health_change", "sick", "mood")
arcs_out = []
for grp, start in ARC_LINES.items():
    n, k = start + 1, 0
    while L(n).startswith(" - "):
        k += 1
        t = L(n)[3:]
        arcs_out.append({"id": f"le_arc_{grp.lower()}_{k:02d}", "group": grp.lower(), "text": t, "src": src(n),
                         "effects": ARC_EFFECTS.get(t, []), "tags": ARC_TAGS.get(t, []),
                         "protection": "allow" if any(e["do"] in HARM for e in ARC_EFFECTS.get(t, [])) else "auto"})
        n += 1
assert len(arcs_out) == 38
arc_by_text = {a["text"]: a for a in arcs_out}
assert all(t in arc_by_text for t in list(ARC_EFFECTS) + list(ARC_TAGS))

# ---------------------------------------------------------------- MIX and choice sets
FRAME_RE = re.compile(r"^SETUP: (.+?) (A|An) ([a-z]+) (an? .+?) and (a|an) ([a-z]+) (an? .+?) disagree about what should "
                      r"happen next\. Their status alone does not settle the matter\.$")
role_by_text = {r["text"]: r for r in roles_out}
pers_by_text = {p["text"]: p for p in pers_out}
seed_by_code = {s["code"]: s for s in seeds_out}
choice_lines = {}   # text -> (id, line)
choice_sets = {}    # tuple of 4 texts -> dict
mix_out = []
n = 24094
while n <= 25112:
    m = re.match(r"^MIX-(\d{3}) — (.+)$", L(n))
    if not m:
        n += 1
        continue
    num, title = m[1], m[2]
    sm = re.match(r"^SOURCE SEED: ([A-Z]{3}-\d\d) \| LENS: (.+)$", L(n + 1))
    code, lens_text = sm[1], sm[2]
    fm = FRAME_RE.match(L(n + 2))
    assert fm, L(n + 2)
    seed = seed_by_code[code]
    assert fm[1] == seed["text"], (num, fm[1])
    assert title == seed["text"].rstrip(".").upper(), (num, title)
    ra, rb = role_by_text[fm[4]], role_by_text[fm[7]]
    pa, pb = pers_by_text[fm[3]], pers_by_text[fm[6]]
    choices, outcomes, texts = [], [], []
    for i, letter in enumerate("ABCD"):
        cl = n + 3 + 3 * i
        cm = re.match(rf"^ {letter}\. (.+)$", L(cl))
        ct = cm[1]
        texts.append(ct)
        if ct not in choice_lines:
            choice_lines[ct] = cl
        pair = []
        for j in (1, 2):
            om = re.match(rf"^  {letter}{j}\. (.+)$", L(cl + j))
            pair.append({"archetype": arc_by_text[om[1]]["id"], "src": src(cl + j)})
        outcomes.append(pair)
        choices.append({"line_src": src(cl)})
    assert L(n + 15).startswith("ADAPTATION: ")
    key = tuple(texts)
    choice_sets.setdefault(key, {"cats": set(), "mix": []})
    choice_sets[key]["cats"].add(seed["category"])
    choice_sets[key]["mix"].append(num)
    mix_out.append({"id": f"le_mix_{num}", "code": f"MIX-{num}", "title": title, "title_src": src(n),
                    "seed": seed["id"], "seed_src": src(n + 1), "category_lens": lens_text,
                    "setup_src": src(n + 2),
                    "first": {"personality": pa["id"], "role": ra["id"]},
                    "second": {"personality": pb["id"], "role": rb["id"]},
                    "choices": [{"choice": None, "src": c["line_src"]} for c in choices],
                    "_texts": texts, "outcomes": outcomes, "adaptation_src": src(n + 15)})
    n += 16
assert len(mix_out) == 60 and len(choice_sets) == 7, (len(mix_out), len(choice_sets))
CHOICE_TAGS = {"Laugh along if nobody is hurt.": ["comedic", "mocking"],
               "Invite everyone to improvise a solution.": ["play"],
               "Let the person most embarrassed decide.": ["comedic"],
               "Ask what the person involved actually wants.": ["consent"]}
cs_out, cline_out, cline_id = [], [], {}
for key, v in choice_sets.items():
    cats = sorted(v["cats"])
    sid = "le_cs_" + "_".join(c.split("_")[-1] for c in cats)
    lines = []
    for i, t in enumerate(key):
        cid = f"{sid}_{'abcd'[i]}"
        cline_id[t] = cid
        cline_out.append({"id": cid, "text": t, "src": src(choice_lines[t]), "set": sid,
                          "tags": CHOICE_TAGS.get(t, [])})
        lines.append(cid)
    cs_out.append({"id": sid, "categories": cats, "choices": lines, "first_mix": f"MIX-{v['mix'][0]}"})
used_cats = {c for s in cs_out for c in s["categories"]}
assert used_cats == {c["id"] for c in categories_out}, used_cats
# a category maps to exactly one set
for c in categories_out:
    c["choice_set"] = next(s["id"] for s in cs_out if c["id"] in s["categories"])
for mx in mix_out:
    for c, t in zip(mx["choices"], mx.pop("_texts")):
        c["choice"] = cline_id[t]

# ---------------------------------------------------------------- compatibility (owner rule 2026-11-14)
def by_tag(items, tag):
    return sorted(i["id"] for i in items if tag in i["tags"])

# Owner decision (2026-11-15): the mixer keeps everything except combinations that produce obviously problematic power
# dynamics, invalidate someone's pain or trauma, portray anyone as lesser, or a minor-adult romance or power imbalance;
# genuine contradictions stay prevented (coherence).  Only the rules those need remain.
RULES = [
    {"id": "C3", "why": "Medical seeds never have the chief decide a villager's care (an obviously problematic power "
                        "dynamic).",
     "seeds_with_any": ["medical"],
     "exclude": {"approaches": sorted(a["id"] for a in apps_out if a["kind"] == "authority")}},
    {"id": "C6", "why": "Purely personal seeds never take prayer, magic, animal labour or experiments "
                        "(source L23825: nonsensical options for a purely personal issue).",
     "seeds_with_any": ["personal"],
     "exclude": {"approaches": sorted(a["id"] for a in apps_out if a["kind"] in ("prayer", "magic", "animal", "experiment"))}},
    {"id": "C9", "why": "Seeds with an adult-only or romantic framing (a love letter, having a child, a child's "
                        "companion, a wedding) never cast a child or a teenager (minor-adult romance).",
     "seeds_with_any": ["adult_only"],
     "exclude": {"roles": sorted(r["id"] for r in roles_out if {"child", "teen"} & set(r["tags"]))}},
]
ROLE_RULES = []
PAIR_RULES = [  # contradictions and repeats in "a <personality> <role>"
    {"id": "P1", "why": "Contradiction or repeat: a devout or skeptical skeptical observer.",
     "role": "le_role_skeptical_observer", "personalities": ["le_pers_devout", "le_pers_skeptical", "le_pers_observant"]},
    {"id": "P2", "why": "Contradiction: a skeptical spiritual elder.", "role": "le_role_spiritual_elder",
     "personalities": ["le_pers_skeptical"]},
    {"id": "P3", "why": "Repeat: a confident confident novice.", "role": "le_role_confident_novice",
     "personalities": ["le_pers_confident"]},
    {"id": "P4", "why": "Contradiction: a confident shy craftsperson.", "role": "le_role_shy_craftsperson",
     "personalities": ["le_pers_confident"]},
]

seed_tags = {s["id"]: set(s["tags"]) for s in seeds_out}
excl = {"seed_approach": {}, "seed_choice": {}, "seed_archetype": {}, "seed_role": {},
        "role_personality": {}, "role_archetype": {}}
KEYMAP = {"approaches": "seed_approach", "choices": "seed_choice", "archetypes": "seed_archetype", "roles": "seed_role"}
for r in RULES:
    for sid, tags in seed_tags.items():
        if sid in r.get("except_seeds", []):
            continue
        hit = (bool(tags & set(r["seeds_with_any"])) if "seeds_with_any" in r else r["seeds_without"] not in tags)
        if hit:
            for k, v in r["exclude"].items():
                excl[KEYMAP[k]].setdefault(sid, set()).update(v)
for r in ROLE_RULES:
    for ro in roles_out:
        if set(ro["tags"]) & set(r["roles_with_any"]):
            for k, v in r["exclude"].items():
                excl["role_archetype" if k == "archetypes" else "role_personality"].setdefault(ro["id"], set()).update(v)
for r in PAIR_RULES:
    excl["role_personality"].setdefault(r["role"], set()).update(r["personalities"])
excl = {k: {i: sorted(v) for i, v in sorted(d.items())} for k, d in excl.items()}

def mix_conflicts(mx):
    out = []
    s = mx["seed"]
    for side in ("first", "second"):
        ro, pe = mx[side]["role"], mx[side]["personality"]
        if ro in excl["seed_role"].get(s, []):
            out.append(f"seed x role {ro}")
        if pe in excl["role_personality"].get(ro, []):
            out.append(f"role {ro} x personality {pe}")
    roles = [mx["first"]["role"], mx["second"]["role"]]
    for c, pair in zip(mx["choices"], mx["outcomes"]):
        if c["choice"] in excl["seed_choice"].get(s, []):
            out.append(f"seed x choice {c['choice']}")
        for o in pair:
            a = o["archetype"]
            if a in excl["seed_archetype"].get(s, []):
                out.append(f"seed x archetype {a}")
            for ro in roles:
                if a in excl["role_archetype"].get(ro, []):
                    out.append(f"role {ro} x archetype {a}")
    return sorted(set(out))

conf = [{"mix": m["id"], "conflicts": c} for m in mix_out if (c := mix_conflicts(m))]

compat = {
    "status": "owner decision (2026-11-15): everything is kept except obviously problematic power dynamics, "
              "invalidating pain or trauma, portraying anyone as lesser, minor-adult romance or power imbalance, "
              "and genuine contradictions",
    "seed_rules": RULES, "role_rules": ROLE_RULES, "pair_rules": PAIR_RULES,
    "exclusions": excl,
    "owner_example_conflicts": conf,
    "owner_example_policy": "The 60 MIX examples are the owner's own text and are kept as written; a MIX listed "
                            "here breaks a rule above and waits for the owner's choice (keep it as variant 0, or "
                            "drop that outcome).",
}

# ---------------------------------------------------------------- MC bank
MC_HEAD = {}
mc_out = []
cur = None
n = 25161
while n <= 25646:
    s = L(n)
    hm = re.match(r"^### (.+) \((\d+) interchangeable situations\)$", s)
    if hm:
        cur = {"heading": hm[1], "src": src(n), "count": int(hm[2])}
        n += 1
        continue
    sm = re.match(r"^\[([A-Z]{3})-(\d\d)\] SETUP: (.+)$", s)
    if sm:
        code = f"{sm[1]}-{sm[2]}"
        cur.setdefault("code", sm[1])
        MC_HEAD[sm[1]] = cur
        apps = []
        for i, letter in enumerate("ABCD"):
            am = re.match(rf"^  {letter}\. (.+)$", L(n + 1 + i))
            apps.append({"id": f"mc_{sm[1].lower()}_{sm[2]}_{letter.lower()}", "letter": letter, "text": am[1],
                         "src": src(n + 1 + i), "outcomes": []})
        mc_out.append({"id": f"mc_{sm[1].lower()}_{sm[2]}", "code": code, "category": "mc_cat_" + sm[1].lower(),
                       "text": sm[3], "src": src(n), "games": [5] if "VV5" in sm[3] else ALL,
                       "vv5_only": "VV5" in sm[3], "approaches": apps, "outcomes_status": "held"})
        n += 5
        continue
    n += 1
assert len(mc_out) == 95

# --- the authored outcome library (L25667-26616): [ID] then A1..D2
FOOD_LOSS = {25680, 25686, 25694, 25714, 25722, 25750, 25890, 25894, 25896, 25914, 25974}
FOOD_GAIN = {25713, 26035, 26079}
TECH = {25895, 25913, 25975}
SKILL = {25739: ["Building"], 25813: ["Building"], 26501: ["Building"], 26511: ["Building"], 26571: ["Building"],
         26573: ["Building"], 26575: ["Building"], 26595: "any"}
CELEBRATE = {25919, 25923, 25981, 26331}
HEALTH = {26440, 26444}
# The owner, 2026-11-17: an outcome whose words give or take The Tree of Life's cloth (a sack is a cloth bolt), soap
# or cutting tools makes it ("supply", docs/event-collection/cie-v6-binary.md 38; scripts/supply_effects.py has the
# collection's).  "A weaver exchanges useful cloth for the fish." / "... ruins a test cloth."
SUPPLY = {25711: ("cloth", 1), 26006: ("cloth", -1)}

def mc_effects(n):
    if n in SUPPLY:
        item, delta = SUPPLY[n]
        return [eff(do="supply", item=item, min=delta, max=delta)]
    if n in FOOD_LOSS:
        return [eff(do="food", size="small", scaled=True, loss=True)]
    if n in FOOD_GAIN:
        return [eff(do="food", size="small", scaled=True)]
    if n in TECH:
        return [eff(do="tech", size="small", scaled=True)]
    if n in SKILL:
        return [eff(do="skill", role="subject", skills=SKILL[n], size="small")]
    if n in CELEBRATE:
        return [eff(do="celebrate", who="all")]
    if n in HEALTH:
        return [eff(do="health_change", role="subject", min=-10, max=-5)]
    return []

assert L(25667).startswith("AUTHORED OUTCOME LIBRARY")
mc_by_code = {m["code"]: m for m in mc_out}
n, n_out = 25668, 0
while n <= 26616:
    hm = re.match(r"^\[([A-Z]{3}-\d\d)\]$", L(n))
    if not hm:
        assert not L(n).strip(), (n, L(n))
        n += 1
        continue
    sit = mc_by_code[hm[1]]
    assert not sit["approaches"][0]["outcomes"], hm[1]
    sit["outcomes_src"] = src(n)
    for i in range(8):
        ln = n + 1 + i
        om = re.match(r"^  ([A-D])([12])\. (.+)$", L(ln))
        assert om and om[1] == "ABCD"[i // 2] and int(om[2]) == i % 2 + 1, (ln, L(ln))
        ef = mc_effects(ln)
        sit["approaches"][i // 2]["outcomes"].append(
            {"id": f"{sit['id']}_{om[1].lower()}{om[2]}", "text": om[3], "src": src(ln), "effects": ef,
             "weight": 1, "protection": "allow" if any(e["do"] in HARM for e in ef) else "auto"})
        n_out += 1
    n += 9
assert n_out == 760 and all(len(a["outcomes"]) == 2 for m in mc_out for a in m["approaches"])
for m in mc_out:
    m["outcomes_status"] = "active"
    t = m["text"]
    if m["code"].startswith("LOS") or re.search(r"\b(visitor|stranger|traveler)\b", t):
        m["subject"] = {"kind": "stranger", "sex": "random"}
    elif re.search(r"\bchild\b", t):
        m["subject"] = {"kind": "villager", "min_age": 3, "max_age": 13}
    else:
        m["subject"] = {"kind": "villager", "min_age": 14}
# no effect may land on a stranger
for m in mc_out:
    for a in m["approaches"]:
        for o in a["outcomes"]:
            if any(e.get("role") == "subject" for e in o["effects"]):
                assert m["subject"]["kind"] == "villager", o["id"]
for k, h in MC_HEAD.items():
    assert sum(1 for m in mc_out if m["code"].startswith(k)) == h["count"]
mc_cats = [{"id": "mc_cat_" + k.lower(), "code": k, "heading": h["heading"], "src": h["src"], "count": h["count"],
            "strangers_are_stranger_roles": k == "LOS",
            "tags": ["somber"] if k in ("DIS", "AFT", "LOS", "TRA") else [], "mood": MC_MOOD[k]}
           for k, h in MC_HEAD.items()]

# ---------------------------------------------------------------- MJ bank (L26617-26867), held
assert L(26619).startswith("MODULAR COMPANION: MYSTERIES")
mj_out = []
n = 26624
while n <= 26867:
    hm = re.match(r"^\[([A-Z]{3})-(\d\d)\] (.+)$", L(n))
    if not hm:
        assert not L(n).strip(), (n, L(n))
        n += 1
        continue
    sm = re.match(r"^SETUP: (.+)$", L(n + 1))
    apps = []
    for i, letter in enumerate("ABCD"):
        am = re.match(rf"^  {letter}\. (.+)$", L(n + 2 + i))
        apps.append({"id": f"mj_{hm[1].lower()}_{hm[2]}_{letter.lower()}", "letter": letter, "text": am[1],
                     "src": src(n + 2 + i), "outcomes": []})
    mj_out.append({"id": f"mj_{hm[1].lower()}_{hm[2]}", "code": f"{hm[1]}-{hm[2]}", "title": hm[3], "title_src": src(n),
                   "text": sm[1], "src": src(n + 1), "games": ALL, "approaches": apps, "outcomes_status": "held"})
    n += 6
assert len(mj_out) == 35, len(mj_out)
mj = {"status": "held: no outcomes yet ('to be developed', L26620); parsed and tested, never drawn",
      "heading": {"text": L(26619), "src": src(26619)},
      "contract": {"text": L(26622).split(": ", 1)[1], "src": src(26622)},
      "contract_checks": ["no harmful effects (no kill, vanish, die_unrecovered, sick, health loss, mood bad)",
                          "no diagnostic labels in any joining words",
                          "no supernatural confirmation (no archetype tagged resolves)",
                          "detention is text only (no effect)",
                          "a suspected crime stays unproven: no outcome names a culprit by role"],
      "seeds": mj_out}

def pool(line, label):
    body = L(line).split(": ", 1)
    assert body[0] == label, body[0]
    items = re.sub(r"\.$", "", body[1]).split("; ")
    return [{"id": f"{slug(label)}_{i + 1:02d}", "text": t, "src": src(line)} for i, t in enumerate(items)]

mc_pools = {"location": pool(25156, "LOCATION POOL"), "participants": pool(25157, "PARTICIPANTS POOL"),
            "outcome_dimensions": pool(25158, "OUTCOME DIMENSIONS")}
assert [len(v) for v in mc_pools.values()] == [20, 23, 15]
contract = [{"id": f"mc_contract_{i}", "src": src(25140 + i), "text": L(25140 + i)} for i in range(1, 11)]
assert all(c["text"].startswith(f"{i}. ") for i, c in enumerate(contract, 1))

# SENSITIVITY EDITS to the owner's text (owner world rules, 2026-11-14): legendary creatures, afterlife concepts and
# ideas such as cannibals or headhunters are never named outright, only described or hinted at.  The smallest piece
# changed; `source_text` keeps the owner's words (living-events.md section 7, listed for the owner's review).
# Lead decision (2026-11-15, the owner's precedent: "Monster" and "afterlife" kept as written; minimal edits): the
# two W1 edits (le_bel_05 "cryptid", mc_aft_09 "monsters") are reverted; the table stays for any future edit.
TEXT_EDITS: dict[str, tuple[str, str, str]] = {}
for item in seeds_out + mc_out:
    if item["id"] in TEXT_EDITS:
        before, after, rule = TEXT_EDITS[item["id"]]
        assert item["text"] == before, (item["id"], item["text"])
        item["text"] = after
        item["source_text"] = before
        item["sensitivity_edit"] = rule

frame_src = mix_out[0]["setup_src"]
bank = {
    "format": "vvfp-living-bank", "version": 1,
    "source": {"path": SRC_REL, "sha256_file": "data/living_events/SOURCE.sha256",
               "living_lines": [23812, 25133], "mc_lines": [25134, 26616], "mj_lines": [26617, 26867]},
    "credit": {"text": L(23815).split(": ", 1)[1], "src": src(23815)},
    "counts": {"seeds": 120, "categories": 12, "roles": 30, "personalities": 24, "lenses": 15, "approaches": 34,
               "archetypes": 38, "choice_sets": 7, "choices": 28, "mix": 60, "mc_situations": 95,
               "mc_approaches": 380, "mc_outcomes": 760, "mc_locations": 20, "mc_participants": 23,
               "mc_outcome_dimensions": 15, "mj_seeds": 35, "mj_approaches": 140},
    "frame": {
        "source_template": "{seed} {PA_Art} {pa} {role_a} and {pb_art} {pb} {role_b} disagree about what should "
                           "happen next. Their status alone does not settle the matter.",
        "source_template_note": "As the 60 MIX SETUP lines read: the capital A, the second a, the role's own "
                                "article (role_a / role_b are the role bank's text with its article).",
        "src": frame_src,
        "fixed_text": "disagree about what should happen next. Their status alone does not settle the matter.",
        "shipped_template": "{seed} (first), {pa_art} {pa} {word_a}, and (second), {pb_art} {pb} {word_b}, disagree "
                            "about what should happen next. Their status alone does not settle the matter.",
        "shipped_note": "Owner 2026-11-14: names are shown. (first) / (second) are the two cast villagers' names; "
                        "{pa_art} is the personality's article (a / an); {word_a} is the role without its article. "
                        "Later references use role pronoun tokens (first.he/she), or the name where a pronoun would "
                        "be ambiguous. Grammar fix id: living-frame-article.",
        "grammar_fix": "living-frame-article",
    },
    "moods": {"order": list(MOODS), "src": "Isola_Complete_Anthology.txt L7-131 (Global Editorial Override, item 10)",
              "note": "pack seed record byte +12: 0 warm, 1 social, 2 serious (living-pack.md 2.2, 4.1a)"},
    "categories": categories_out,
    "seeds": seeds_out,
    "roles": roles_out,
    "personalities": pers_out,
    "lenses": lens_out,
    "approaches": apps_out,
    "archetypes": arcs_out,
    "choice_sets": cs_out,
    "choices": cline_out,
    "mix": mix_out,
    "compat": compat,
    "rare_roll": {"series": "category", "note": "owner 2026-11-14: each category counts as one series"},
    "mc": {"status": "active: 760 authored outcomes (L25667-26616)",
           "credit_question": "Q11",
           "outcome_library": {"text": L(25667), "src": src(25667)},
           "effect_rule": "owner 2026-11-14: effects follow what each outcome line says (death, disappearance, "
                          "injury or illness where the line says so, including children and nursing parents with "
                          "protection allow); no line in the library implies a death or a disappearance",
           "contract": contract, "pools": mc_pools, "categories": mc_cats, "situations": mc_out},
    "mj": mj,
}
out = ROOT / "data" / "living_events" / "bank.json"
out.write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("written", out)
print("choice sets:", [(c["id"], c["first_mix"]) for c in cs_out])
print("mix conflicts:", len(conf))
for c in conf:
    print(" ", c["mix"], c["conflicts"])
print("exclusion counts:", {k: sum(len(v) for v in d.values()) for k, d in excl.items()})
