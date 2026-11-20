"""Write the owner-approved draft event files, group C (collection_lib.DRAFTS_C: Healing, Psychology and Medicine
HEA, Advice and Decisions ADV, Relationships, Singlehood and Family FAM2, Belief and Identity BLF, Nature, Ecology
and Animals NAT, Disability and Diversity DIV, History and Collective Memory HIS, Pondering How Life Has Gone LIF;
50 events each) as collection events, then format and check them:

    python scripts/drafts_c/gen_drafts_c.py [prefix ...]

Built as group B (scripts/drafts_b/gen_drafts_b.py, whose rules hold here): the setup is the question page with the
draft's labels; each label leads to its own one outcome page; a single-popup event is one page.  The casting line is
a ledger note carried out as the roles' ages; an "[effect: ...]" is cut from its outcome and made as its effect.

GROUP C ADDS (the owner and the drafts' own notes, 2026-11-15):
- (name3) / (name4) are the roles "third" / "fourth"; HEA-15 offers three choices.
- "where the game records it": the relation is cast where the game records one (cie-v6-binary.md 21, the annotation's
  REL line); the text is unchanged either way.  The engine has no "prefer" relation: the rare roll and Pick Island
  Event draw such an event only where the relation holds; bought through the library, a relation nobody meets is
  dropped and any fitting villager is cast.
- A heading's "(VV5 only)" makes the row New Believers only (collection_manifest.DRAFTS_C_VV5_TAG); BLF-26/27's Isolan
  is a named stranger (authoring-rules.md 15: Isolans are never cast).
- Tree of Life Supplies (SUP, the owner's request of 2026-11-17): every heading is "(VV4 only)" (The Tree of Life only,
  collection_manifest.DRAFTS_C_VV4_TAG); an "[effect: the village gains / loses N cutting tools / bars of soap /
  cloth bolts]" is the "supply" effect (cie-v6-binary.md 38), and one bracket may hold several effects ("; ").
- The owner's orders as group B: text verbatim; things need not exist in the game to appear in the text; a person
  named only by a role word is a cast villager shown by name (a ledger "sensitivity" entry each).

FORMAT LIMIT: no "his/hers" placeholder, so a "(his/hers)" is "(his/her) own" (or the noun the sentence means,
HISHERS_AT), each a grammar-fixes.md row.

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drafts_c_parse as P  # noqa: E402

lib = P.lib
sys.path.insert(0, str(P.ROOT / "scripts"))
import collection_check as cc  # noqa: E402
sys.path.insert(0, str(P.ROOT / "scripts" / "drafts_b"))
from gen_drafts_b import age_spec, escape_parens as _escape_b, text_only  # noqa: E402,F401

FIG_TOKEN = re.compile(r"\[([a-z0-9]):(he/she|He/she|him/her|his/her|His/her)\]|\[([a-z0-9])\]")
HISHERS = ("(his/hers)", "(his/her) own")
HISHERS_AT = {("draft_div", "DIV-39"): ("(his/hers)", "(his/her) fault")}   # (source id, code) -> where "own" fails
ROLE_FOR = {"1": "subject", "2": "friend", "3": "third", "4": "fourth", "s": "other"}
GAME_NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
              5: "New Believers"}
RELATIONS = ("spouse_of", "parent_of", "child_of", "sibling_of", "grandparent_of", "grandchild_of",
             "aunt_or_uncle_of", "cousin_of")


def _skill(role: str, skills: list[str]) -> dict:
    lo, hi = cc.SKILL_SIZES["small"]
    return {"do": "skill", "role": role, "skills": skills, "min": lo, "max": hi}


def _health(role: str, sign: int) -> list[dict]:
    return [{"do": "health_change", "role": role, "min": 10 * sign if sign > 0 else -30,
             "max": 30 if sign > 0 else -10}]


EFFECTS = {
    "small food gain": [{"do": "food", "size": "small", "scaled": True}],
    "small food loss": [{"do": "food", "size": "small", "scaled": True, "loss": True}],
    "(name1) gains health": _health("subject", 1),
    "(name2) gains health": _health("friend", 1),
    "(name1) loses a little health": _health("subject", -1),
    "(name2) loses a little health": _health("friend", -1),
    "small health loss for (name2)": _health("friend", -1),
    "small Healing skill for (name1), only where the game has it": [_skill("subject", ["Healing"])],
    "small Healing skill for (name2), only where the game has it": [_skill("friend", ["Healing"])],
    "small skill gain for (name2) in the game's crafting or building skill, only where the game has one":
        [_skill("friend", ["Building"])],
    "(name1) celebrates": [{"do": "celebrate", "who": "subject"}],
    "(name2) celebrates": [{"do": "celebrate", "who": "friend"}],
    "(name1) and (name2) celebrate": [{"do": "celebrate", "who": "subject"}, {"do": "celebrate", "who": "friend"}],
    "small research or tech gain, only where the game has it": [{"do": "tech", "size": "small", "scaled": True}],
    "small tech gain, only where the game has tech points": [{"do": "tech", "size": "small", "scaled": True}],
}
# DIV-27's "small skill gain for (name1)": the annotation's SKILL line names the skill (the draft names none)
EFFECT_RE = re.compile(r"\s*\[effect: ([^\]]+)\]")
OWN_GENERATOR = {"draft_trd": "scripts/drafts_c/gen_traders.py"}   # built by its own generator
# Living Culture (LCA..): each ending's "[Solidarity: raise|lower|neutral]" tag (the owner, 2026-11-17: solidarity is a
# planned village counter that only changes the odds of later events; no engine effect yet), cut as a note.
SOLIDARITY_RE = re.compile(r"\s*\[Solidarity: (raise|lower|neutral)\]")
# Living Culture's general effect words (the role is (name1)..(name4); Devotion falls back to the named skill outside
# New Believers, the style guide's 8b)
ROLE_WORD = {"1": "subject", "2": "friend", "3": "third", "4": "fourth"}
SKILL_RE = re.compile(r"(small|moderate) (Farming|Building|Healing|Research|Parenting|Devotion)"
                      r"(?: or (Farming|Building|Healing|Research|Parenting))? skill for \(name([1-4])\)")
HEALTH_RE = re.compile(r"\(name([1-4])\) (gains health|loses a little health|loses health)")
CELEBRATE_RE = re.compile(r"\(name([1-4])\) celebrates|everyone celebrates")


def _general_effect(what: str) -> list[dict] | None:
    m = SKILL_RE.fullmatch(what)
    if m:
        skills = [m.group(2)] + ([m.group(3)] if m.group(3) else [])
        lo, hi = cc.SKILL_SIZES["small" if m.group(1) == "small" else "normal"]
        return [{"do": "skill", "role": ROLE_WORD[m.group(4)], "skills": skills, "min": lo, "max": hi}]
    m = HEALTH_RE.fullmatch(what)
    if m:
        role = ROLE_WORD[m.group(1)]
        if m.group(2) == "gains health":
            return _health(role, 1)
        if m.group(2) == "loses a little health":
            return _health(role, -1)
        return [{"do": "health_change", "role": role, "min": -50, "max": -30}]
    m = CELEBRATE_RE.fullmatch(what)
    if m:
        return [{"do": "celebrate", "who": ROLE_WORD[m.group(1)] if m.group(1) else "all"}]
    for size in ("small", "normal"):
        for kind in ("food", "tech"):
            for sign, loss in (("gain", False), ("loss", True)):
                if what == f"{size} {kind} {sign}" and not (size == "small" and kind == "food"):
                    return [dict({"do": kind, "size": size, "scaled": True}, **({"loss": True} if loss else {}))]
    return None


# Tree of Life Supplies (draft_sup): "the village gains 2 cutting tools", "loses 1 bar of soap", "gains 1 cloth bolt"
# -- the "supply" effect (docs/event-collection/cie-v6-binary.md 38; a sack is a cloth bolt).
SUPPLY_RE = re.compile(r"the village (gains|loses) (\d+)(?: to (\d+))? (cutting tools?|bars? of soap|cloth bolts?)")
SUPPLY_WORDS = {"cutting tool": "cutting_tools", "bar of soap": "soap", "cloth bolt": "cloth"}


def _supply(m: re.Match) -> dict:
    lo = int(m.group(2))
    hi = int(m.group(3)) if m.group(3) else lo
    noun = re.sub(r"^(cutting tool|bar|cloth bolt)s?", r"\1", m.group(4))
    item = SUPPLY_WORDS[noun]
    return ({"do": "supply", "item": item, "min": lo, "max": hi} if m.group(1) == "gains"
            else {"do": "supply", "item": item, "min": -hi, "max": -lo})


# Island Traders (draft_trd, cie-v6-binary.md 39): "trade 150 food for 400 tech points".
TRADE_RE = re.compile(r"trade (\d+) ([a-z ]+?) for (\d+) ([a-z ]+)")
GOOD_WORDS = {"food": "food", "tech points": "tech", "berries": "berries", "coconuts": "coconuts", "fish": "fish",
              "collectible": "collectible", "collectibles": "collectible", "honey": "honey", "fruit": "fruit",
              "blackberries": "blackberries", "noni": "noni", "cloth bolts": "cloth", "cutting tools": "cutting_tools",
              "bars of soap": "soap"}


# Village Moments (draft_vfx, cie-v6-binary.md 40-41): group behaviours, songs, the weather, the village.
GROUP_VERBS = {"sings": "song", "chants": "chant", "dances": "dance", "relaxes": "relax", "swims": "swim",
               "prays": "pray", "celebrates": "celebrate", "gives a speech": "speech"}
VILLAGE_FX_RE = re.compile(
    r"the whole village (?P<all>sings|chants|dances|relaxes|swims|prays|celebrates)"
    r"|\(name(?P<who>[12])\) (?P<one>sings|chants|dances|gives a speech)"
    r"|the (?P<kids>children play|elders tell stories)"
    r"|(?P<weather>rain|a storm|fog|sunshine|clear skies) starts?"
    r"|the next island event comes (?P<hours>\d+) hours (?P<dir>sooner|later)"
    r"|a random tech level (?P<lvl>rises|falls) by 1"
    r"|a hut being built gains (?P<pts>\d+) points"
    r"|(?P<pct>\d+) in 100 villagers fall sick"
    r"|(?P<cure>every villager is cured)"
    r"|the (?P<work>farming|building|research|healing|parenting|devotion) workers rush to work"
    r"|(?P<spawn>the island scatters new things to find)"
    r"|\(name(?P<twho>[12])\) (?:gets the |is made |is covered in )(?P<temp>hiccups|clean|gunk)")
TEMP_WORDS = {"hiccups": "hiccups", "clean": "clean", "gunk": "gunk"}
WEATHER_WORDS = {"rain": "rain", "a storm": "storm", "fog": "fog", "sunshine": "sun", "clear skies": "clear"}


def _village_fx(m: re.Match) -> dict:
    if m.group("all"):
        return {"do": "group", "kind": GROUP_VERBS[m.group("all")], "who": "all"}
    if m.group("one"):
        return {"do": "group", "kind": GROUP_VERBS[m.group("one")], "who": ROLE_FOR[m.group("who")]}
    if m.group("kids"):
        return {"do": "group", "kind": "play" if m.group("kids").startswith("children") else "stories", "who": "all"}
    if m.group("weather"):
        return {"do": "village", "what": "weather", "weather": WEATHER_WORDS[m.group("weather")]}
    if m.group("hours"):
        h = int(m.group("hours")) * (-1 if m.group("dir") == "sooner" else 1)
        return {"do": "village", "what": "event_timer", "min": h, "max": h}
    if m.group("lvl"):
        return {"do": "village", "what": "tech_level", "step": 1 if m.group("lvl") == "rises" else -1}
    if m.group("pts"):
        return {"do": "village", "what": "construction", "min": int(m.group("pts")), "max": int(m.group("pts"))}
    if m.group("work"):
        return {"do": "group", "kind": "work", "skill": m.group("work").capitalize(), "who": "all"}
    if m.group("spawn"):
        return {"do": "village", "what": "spawn"}
    if m.group("twho"):
        return {"do": "group", "kind": "effect", "effect": TEMP_WORDS[m.group("temp")], "who": ROLE_FOR[m.group("twho")]}
    if m.group("pct"):
        return {"do": "group", "kind": "sick", "who": "all", "percent": int(m.group("pct"))}
    return {"do": "group", "kind": "cure", "who": "all"}


def effect_for(code: str, what: str, ann: dict) -> list[dict]:
    if "; " in what:                   # several effects in one bracket (draft_sup)
        return [e for part in what.split("; ") for e in effect_for(code, part, ann)]
    m = SUPPLY_RE.fullmatch(what)
    if m:
        return [_supply(m)]
    m = VILLAGE_FX_RE.fullmatch(what)
    if m:
        return [_village_fx(m)]
    m = TRADE_RE.fullmatch(what)
    if m:
        return [{"do": "trade", "give": GOOD_WORDS[m.group(2)], "give_amount": int(m.group(1)),
                 "get": GOOD_WORDS[m.group(4)], "get_amount": int(m.group(3))}]
    if what in EFFECTS:
        return [dict(e) for e in EFFECTS[what]]
    gen = _general_effect(what)
    if gen is not None:
        return gen
    if what == "small skill gain for (name1)":
        return [_skill("subject", ann["SKILL"].split(","))]
    raise SystemExit(f"{code}: no effect for {what!r}")


def L(n: int) -> str:
    return f"L{n}"


def escape_parens(text: str) -> str:
    keep = re.compile(r"\((?:name[1-4]|he/she|He/she|him/her|his/her|His/her)\)|\{@[A-Za-z]+\}")
    out, i = [], 0
    for m in keep.finditer(text):
        out.append(text[i:m.start()].replace("(", r"\(").replace(")", r"\)"))
        out.append(m.group(0))
        i = m.end()
    out.append(text[i:].replace("(", r"\(").replace(")", r"\)"))
    return "".join(out)


def role_spec(spec: str) -> dict:
    """"18+", "3-13"; "/f" "/m" a sex; "/nursing" the nursing parent (special); "~2" at most 2 years from the
    subject; "stranger" a named outsider."""
    if spec == "stranger":
        return {"kind": "stranger", "sex": "random", "named": True}
    gap = None
    if "~" in spec:
        spec, years = spec.split("~")
        gap = {"role": "subject", "years": int(years)}
    if spec.endswith("/nursing"):
        out = age_spec(spec[:-len("/nursing")])
        out["special"] = "nursing_parent"
        return out
    sex = None
    if "/" in spec:
        spec, sx = spec.split("/")
        sex = {"f": "female", "m": "male"}[sx]
    out = age_spec(spec)
    if sex:
        out["sex"] = sex
    if gap:
        out["max_age_gap"] = gap
    return out


def build(ev: P.Event, ann: dict) -> tuple[dict, list[str], list[dict]]:
    sid, row = ev.sid, ev.row
    problems: list[str] = []
    figs = {}
    for item in ann.get("FIG", "").split():
        letter, rest = item.split("=", 1)
        rid, age = rest.split(":", 1)
        figs[letter] = (rid, age)
    role_of = dict(ROLE_FOR, **{k: v[0] for k, v in figs.items()})
    edits: dict[str, list[tuple[str, str]]] = {}
    for part, before, after in ann.get("EDITS", []):
        edits.setdefault(part, []).append((before, after))
    ledger = [{"src": L(ev.picks), "kind": "note",
               "why": "the casting line, carried out as the roles' ages (" + P.raw(sid, ev.picks).strip("()") + ")"}]
    if row["games"] == [5]:
        ledger.append({"src": L(row["lines"][0]), "kind": "note",
                       "why": "the heading's \"(VV5 only)\": the event is New Believers only"})
    elif row["games"] == [4]:
        ledger.append({"src": L(row["lines"][0]), "kind": "note",
                       "why": "the heading's \"(VV4 only)\": the event is The Tree of Life only"})
    elif len(row["games"]) == 1:
        g1 = row["games"][0]
        ledger.append({"src": L(row["lines"][0]), "kind": "note",
                       "why": f"the heading's \"(VV{g1} only)\": the event is {GAME_NAMES[g1]} only"})
    grammar, gfix_rows, nodes_fx, texts = [], [], {}, {}
    for k, n in ev.parts.items():
        s = P.raw(sid, n)
        fx = []
        m = EFFECT_RE.search(s)
        if m:
            fx = effect_for(ev.code, m.group(1), ann)
            ledger.append({"src": L(n), "kind": "instruction", "text": m.group(0).strip(),
                           "why": "the draft's effect, never shown: the outcome's effect"})
            s = s[:m.start()] + s[m.end():]
        m = SOLIDARITY_RE.search(s)
        if m:
            ledger.append({"src": L(n), "kind": "note", "text": m.group(0).strip(),
                           "why": "the ending's Solidarity tag (planned village counter; never shown, no effect yet)"})
            s = s[:m.start()] + s[m.end():]
        if HISHERS[0] in s:
            fix = HISHERS_AT.get((sid, ev.code), HISHERS)
            while fix[0] in s:
                grammar.append({"src": L(n), "before": fix[0], "after": fix[1]})
                gfix_rows.append({"line": n, "before": fix[0], "after": fix[1], "code": ev.code})
                s = s.replace(fix[0], fix[1], 1)
        for before, after in edits.get(k, []):
            if s.count(before) != 1:
                problems.append(f"{ev.code} {k}: edit before {before!r} occurs {s.count(before)} times")
                continue
            s = s.replace(before, after)
            src_after = FIG_TOKEN.sub(lambda mm: f"({role_of[mm.group(1)]}.{mm.group(2)})" if mm.group(1)
                                      else f"({role_of[mm.group(3)]})", after)
            ledger.append({"src": L(n), "kind": "sensitivity",
                           "before": lib.normalize_source_text(before.replace(*HISHERS)),
                           "after": lib.normalize_source_text(src_after),
                           "why": "the owner (2026-11-15): a person named by a role word is a cast villager and "
                                  "shows the name (flavor only: the villager need not have that job)"})
        if ann.get("WORD") == "chief":
            s = re.sub(r"\bchief\b", "{@chief}", s)
            s = re.sub(r"\bChief\b", "{@Chief}", s)
        s = lib.normalize_source_text(s)
        nodes_fx[k] = fx
        texts[k] = s
    mk = P.marks(ev, ann)
    for k, s in texts.items():
        found = P.PRONOUN_RE.findall(s)
        if len(found) != len(mk[k]):
            problems.append(f"{ev.code} {k}: {len(found)} pronouns, {len(mk[k])} marks")
    names_used = set(P.NAME_RE.findall(" ".join(texts.values()) + " " + row["title"]))
    marks_all = "".join(mk.values())
    names_used |= {c for c in marks_all if c in "1234"}
    names_used |= {m.group(1) or m.group(3) for m in FIG_TOKEN.finditer(" ".join(texts.values())) if (m.group(1) or m.group(3)) in "1234"}
    names_used.add("1")
    ages = ann.get("ROLES", {})
    roles: dict = {}
    for d in sorted(names_used):
        spec = ages.get(f"name{d}")
        if spec is None:
            problems.append(f"{ev.code}: no ROLES entry for name{d}")
            spec = "18+"
        roles[ROLE_FOR[d]] = role_spec(spec)
    for key, val in ann.get("REL", {}).items():
        kind, other = val.split(":")
        assert kind in RELATIONS, (ev.code, kind)
        roles[ROLE_FOR[key[-1]]]["relation"] = {kind: ROLE_FOR[other[-1]]}
    for letter, (rid, age) in figs.items():
        roles[rid] = role_spec(age)
    if "s" in marks_all:
        roles["other"] = {"kind": "stranger", "sex": "random"}
    multi = len(roles) > 1
    shown = {}
    for k, s in texts.items():
        it = iter(mk[k])
        s = escape_parens(s)

        def pron(mm, it=it):
            who = role_of[next(it)]
            return f"({who}.{mm.group(1)})" if multi else mm.group(0)
        s = P.PRONOUN_RE.sub(pron, s)
        if multi:
            s = P.NAME_RE.sub(lambda mm: f"({ROLE_FOR[mm.group(1)]})", s)
        s = FIG_TOKEN.sub(lambda mm: f"({role_of[mm.group(1)]}.{mm.group(2)})" if mm.group(1)
                          else f"({role_of[mm.group(3)]})", s)
        if k.startswith("L"):
            s = lib.title_case_label(s.rstrip().rstrip(":"))
        shown[k] = s
    desc = ann.get("DESC", "")
    if not (cc.DESCRIPTION_RE.fullmatch(desc) and len(desc) <= cc.DESCRIPTION_MAX):
        problems.append(f"{ev.code}: description {desc!r}")

    def page(k: str, name: str) -> dict:
        nd = {"name": name, "text": shown[k], "src": L(ev.parts[k])}
        if nodes_fx[k]:
            nd["effects"] = [dict(e, src=L(ev.parts[k])) for e in nodes_fx[k]]
        to = text_only(P.raw(sid, ev.parts[k]), nodes_fx[k])
        if to:
            nd["text_only"] = [dict(t, src=L(ev.parts[k])) for t in to]
        return nd

    if "L1" in ev.parts:
        q = page("S", "The setup")
        pairs = [(lk, "O" + lk[1:]) for lk in ev.parts if lk.startswith("L")]
        q = {"type": "question", **q,
             "choices": [{"label": shown[lk], "next": ok.lower(), "src": L(ev.parts[lk])} for lk, ok in pairs]}
        nodes = {"setup": q}
        for i, (_lk, ok) in enumerate(pairs):
            nodes[ok.lower()] = page(ok, "Outcome " + "ABC"[i])
    else:
        nodes = {"setup": page("S", "The scene")}
    used = {e.get("role") or e.get("who") for nd in nodes.values() for e in nd.get("effects", [])} - {None, "all"}
    col = {"id": row["id"], "title_src": L(row["lines"][0]), "ledger": ledger, "description": desc,
           "label_case": "title"}
    cast_only = [r for r, spec in roles.items() if spec["kind"] == "villager" and r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": row["games"],
           "collection": col,
           "requirement": {"min_eligible": sum(1 for r in roles.values() if r["kind"] == "villager")},
           "roles": roles, "start": "setup", "nodes": nodes}
    if ann.get("NEED"):
        # cie-v6-binary.md 39: offered only when the village has it (VFX-06's cloth bolt)
        item, n = ann["NEED"].split("=")
        doc["requirement"]["if"] = {"has_supply": {"item": item, "min": int(n)}}
    if ann.get("WORD") == "chief":
        if row["games"] == [3]:
            problems.append(f"{ev.code}: a VV3-only event needs no chief word")
        doc["words"] = {"chief": {"3": "chief", "*": "leader"}, "Chief": {"3": "Chief", "*": "Leader"}}
    if grammar:
        doc["grammar_fixes"] = grammar
    return doc, problems, gfix_rows


def same_sex_variants(doc: dict) -> dict:
    """The owner's rule for a same-sex couple: cast by sex, the relationship is text.  The couple (subject, friend)
    becomes two pairs, two men (men1, men2) and two women (women1, women2); the event starts with a branch of two
    equally likely children, each leading to its own copy of the pages.  The checker needs a page for every cast, so
    one pair is needed (the men) and the other optional (the women, whose child is taken only when both are cast):
    where both pairs can be cast the two are equally likely; where no two women can, the men's version shows."""
    import copy
    pairs = {"m": ("men1", "men2", "male"), "f": ("women1", "women2", "female")}
    base = {k: v for k, v in doc["roles"].items() if k not in ("subject", "friend")}
    spec = {k: v for k, v in doc["roles"]["subject"].items()}
    roles = dict(base)
    for a, b, sex in pairs.values():
        roles[a] = dict(spec, sex=sex, **({"optional": True} if sex == "female" else {}))
        roles[b] = dict(spec, sex=sex, **({"optional": True} if sex == "female" else {}))

    def swap(obj, a, b):
        s = json.dumps(obj, ensure_ascii=False)
        s = re.sub(r"\(subject([.)])", rf"({a}\1", s)
        s = re.sub(r"\(friend([.)])", rf"({b}\1", s)
        s = s.replace('"who": "subject"', f'"who": "{a}"').replace('"who": "friend"', f'"who": "{b}"')
        s = s.replace('"role": "subject"', f'"role": "{a}"').replace('"role": "friend"', f'"role": "{b}"')
        return json.loads(s)

    nodes, children = {}, []
    for tag, (a, b, _sex) in pairs.items():
        for k, nd in doc["nodes"].items():
            nd = swap(copy.deepcopy(nd), a, b)
            for c in nd.get("choices", []):
                c["next"] = f"{c['next']}_{tag}"
            nodes[f"{k}_{tag}"] = nd
        children.append({"next": f"{doc['start']}_{tag}"} if tag == "m" else
                        {"next": f"{doc['start']}_{tag}", "if": {"all": [{"role": a}, {"role": b}]}})
    doc = dict(doc, roles=roles, start="pair", nodes={"pair": {"type": "branch", "name": "The couple",
                                                               "children": children}, **nodes})
    doc["requirement"] = {"min_eligible": len(base) + 2}
    col = dict(doc["collection"])
    col["cast_only"] = [r for r in col.get("cast_only", []) if r in roles]
    if not col["cast_only"]:
        col.pop("cast_only")
    col["ledger"] = col["ledger"] + [{"src": col["ledger"][0]["src"], "kind": "note",
                                      "why": "the owner's rule for a same-sex couple: cast by sex (two men or two "
                                             "women, equally likely where both can be cast), the relationship as "
                                             "story text"}]
    doc["collection"] = col
    return doc


def main() -> int:
    docs, problems, gfix = [], [], []
    only = [a.lower() for a in sys.argv[1:]]
    for sid, (_t, _n, sec, pre) in lib.DRAFTS_C.items():
        if (only and pre.lower() not in only) or sid in OWN_GENERATOR:
            continue
        anns = P.read_annotations(sid)
        for ev in P.events(sid):
            doc, probs, g = build(ev, anns.get(ev.code, {}))
            if anns.get(ev.code, {}).get("WORD") == "same_sex":
                doc = same_sex_variants(doc)
            problems += probs
            gfix += [dict(x, sid=sid) for x in g]
            docs.append((lib.DRAFTS_C_DIR / sec / f"{ev.row['id']}.json", doc))
    for p in problems:
        print("PROBLEM", p)
    for g in gfix:
        print(f"GRAMMAR | {g['sid']} L{g['line']} | `{g['before']}` | `{g['after']}` | {g['code']} |")
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    rc = subprocess.call([sys.executable, str(P.ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
