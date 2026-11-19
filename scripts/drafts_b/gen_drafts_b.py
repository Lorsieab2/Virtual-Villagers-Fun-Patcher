"""Write the owner-approved draft event files, group B (collection_lib.DRAFTS_B: Humor and Absurdity HUM, Tall Tales
and Self-Interest TT, Honesty and Accountability HON, Justice and Consequences JUS, Departures and Exile DEP, Dreams
and Ambitions DRM, Fears and Doubts FEA, Good, Bad and Ordinary Days DAY; 50 events each) as collection events, then
format and check them:

    python scripts/drafts_b/gen_drafts_b.py

THE SHAPE (drafts_b_parse.py): the setup is the question page with the draft's two labels; each label leads to its
own one outcome page (the drafts give one outcome per choice, no odds).  A single-popup event is one page with an OK
button.  The casting line is a ledger note carried out as the roles' ages; an "[effect: ...]" is an instruction cut
from its outcome and made as the outcome's effect.

THE OWNER'S ORDERS (2026-11-15): "the drafts are ok as long as they stick to our rules"; preserve the text, edit only
genuine rule breaks (none was found: every event's 15-point review is in the annotations); things need not exist in
the game to appear in the text; and "use names and pronouns where possible instead of vague 'a fisher', 'a healer',
'an elder'": each such role figure is a cast villager (its own harmless role) and its mentions show the name -- each
change is a ledger "sensitivity" entry (before -> after, listed by --report for the owner).

THE ANNOTATIONS (scripts/drafts_b/annotations/<prefix>.txt, drafts_b_parse.read_annotations): whose each pronoun
is, the roles' ages, the role figures and their name edits, the Pick Island Event sentence and the review.

FORMAT LIMIT: there is no "his/hers" placeholder, so the drafts' nine "(his/hers)" are "(his/her) own" (grammar-fixes.md
rows `| draft_<x> L<n> |`).

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drafts_b_parse as P  # noqa: E402

lib = P.lib
sys.path.insert(0, str(P.ROOT / "scripts"))
import collection_check as cc  # noqa: E402

FIG_TOKEN = re.compile(r"\[([a-z0-9]):(he/she|He/she|him/her|his/her|His/her)\]|\[([a-z0-9])\]")
HISHERS = ("(his/hers)", "(his/her) own")
HISHERS_AT = {("draft_hon", 305): ("(his/hers) to mention", "(his/her) place to mention")}
ROLE_FOR = {"1": "subject", "2": "friend", "s": "other"}      # (name1) / (name2) are the format's subject / friend

# ---- Effects: each "[effect: ...]" of the drafts, as the format's effects ----------------------------------------


def _skill(role: str, skills: list[str]) -> dict:
    lo, hi = cc.SKILL_SIZES["small"]
    return {"do": "skill", "role": role, "skills": skills, "min": lo, "max": hi}


EFFECTS = {
    "small food gain": [{"do": "food", "size": "small", "scaled": True}],
    "small food loss": [{"do": "food", "size": "small", "scaled": True, "loss": True}],
    "small health loss for (name1)": [{"do": "health_change", "role": "subject", "min": -30, "max": -10}],
    "small health loss for (name2)": [{"do": "health_change", "role": "friend", "min": -30, "max": -10}],
    # JUS-05: "whichever gardening/farming skill the game has" (the draft's notes)
    "small skill gain for (name1)": [_skill("subject", ["Farming"])],
    "(name1) disappears from the village (no grave); rare": [{"do": "vanish", "role": "subject"}],
    "small Healing skill, only where the game has it": [_skill("subject", ["Healing"])],
    "(name1) celebrates": [{"do": "celebrate", "who": "subject"}],
    "small Building skill, only where the game has one": [_skill("subject", ["Building"])],
    "small tech gain, only where the game has tech points": [{"do": "tech", "size": "small", "scaled": True}],
    # DRM-48: the game does not know a villager's "work": one of the work skills at random
    "small skill gain in (name1)'s work, where the game has one": [
        _skill("subject", ["Farming", "Building", "Healing", "Research"])],
    "(name1) gains health": [{"do": "health_change", "role": "subject", "min": 10, "max": 30}],
}
EFFECT_RE = re.compile(r"\s*\[effect: ([^\]]+)\]")

# Why an effect-table word changes nothing: the drafts' own notes ("Everything else is story only").
STORY_ONLY = "the draft's notes: everything but the marked effects is story only"
WORD_WHY = {
    "food": "food in the story (a meal, a catch, fruit); the village's stores do not change -- " + STORY_ONLY,
    "tech": "technology talked about in the story; no tech points change -- " + STORY_ONLY,
    "skill": "\"experience\" / \"skill\" in the everyday sense, not a skill gain -- " + STORY_ONLY,
    "celebrate": "a celebration or a happy feeling in the story; no celebration happens in the game -- " + STORY_ONLY,
    "health": "health or an injury talked about in the story; nobody's health changes -- " + STORY_ONLY,
    "preference": "a feeling in the moment, not a lasting dislike -- " + STORY_ONLY,
    "kill": "a death only talked about (or the word's everyday sense); nobody dies -- " + STORY_ONLY,
    "vanish": "the word's everyday sense (a thing, a sound or a person out of sight for a moment); nobody leaves "
              "the village -- " + STORY_ONLY,
    "damage": "a small thing breaks in the story; no building is damaged -- " + STORY_ONLY,
}


def kinds(effects: list[dict]) -> set[str]:
    return {cc.EFFECT_KIND.get(e["do"], e["do"]) for e in effects}


def text_only(text: str, effects: list[dict]) -> list[dict]:
    have, out = kinds(effects), []
    for rx, want in cc.KEYWORDS:
        if have & want:
            continue
        words = []
        for m in rx.finditer(text):
            if m.group(0).lower() not in words:
                words.append(m.group(0).lower())
        if words:
            kind = ("health" if "health_change" in want else "kill" if "kill" in want else sorted(want)[0])
            out.append({"what": ", ".join(f'"{w}"' for w in words), "reason": WORD_WHY[kind]})
    return out


# ---- Ages ---------------------------------------------------------------------------------------------------------

def age_spec(spec: str) -> dict:
    m = re.fullmatch(r"(\d+)\+", spec)
    if m:
        return {"kind": "villager", "min_age": int(m.group(1))}
    m = re.fullmatch(r"(\d+)-(\d+)", spec)
    assert m, spec
    return {"kind": "villager", "min_age": int(m.group(1)), "max_age": int(m.group(2))}


# ---- One event ----------------------------------------------------------------------------------------------------

def L(n: int) -> str:
    return f"L{n}"


def escape_parens(text: str) -> str:
    """A literal parenthesis of the draft's prose is \\( \\); the placeholders stay."""
    keep = re.compile(r"\((?:name[12]|he/she|He/she|him/her|his/her|His/her)\)")
    out, i = [], 0
    for m in keep.finditer(text):
        out.append(text[i:m.start()].replace("(", r"\(").replace(")", r"\)"))
        out.append(m.group(0))
        i = m.end()
    out.append(text[i:].replace("(", r"\(").replace(")", r"\)"))
    return "".join(out)


def build(ev: P.Event, ann: dict) -> tuple[dict, list[str]]:
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
    grammar, nodes_fx, texts, used_roles = [], {}, {}, set()
    marks_all = "".join(ann.get(k, "") for k in ev.parts)
    for k, n in ev.parts.items():
        s = P.raw(sid, n)
        fx = []
        m = EFFECT_RE.search(s)
        if m:
            assert m.group(1) in EFFECTS, (ev.code, m.group(1))
            fx = [dict(e) for e in EFFECTS[m.group(1)]]
            ledger.append({"src": L(n), "kind": "instruction", "text": m.group(0).strip(),
                           "why": "the draft's effect, never shown: the outcome's effect"})
            s = s[:m.start()] + s[m.end():]
        if HISHERS[0] in s:
            fix = HISHERS_AT.get((sid, n), HISHERS)
            grammar.append({"src": L(n), "before": fix[0], "after": fix[1]})
            s = s.replace(*fix)
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
        s = lib.normalize_source_text(s)
        nodes_fx[k] = fx
        texts[k] = s
    # whose each pronoun is
    multi = None
    for k, s in texts.items():
        marks = ann.get(k, "")
        found = P.PRONOUN_RE.findall(s)
        if len(found) != len(marks):
            problems.append(f"{ev.code} {k}: {len(found)} pronouns, {len(marks)} marks")
            marks = (marks + "1" * len(found))[:len(found)]
        texts[k] = (s, marks)
    alltext = " ".join(s for s, _ in texts.values())
    villagers = {"subject"} | ({"friend"} if "(name2)" in alltext or "2" in marks_all or "[2:" in alltext else set())
    roles: dict = {}
    ages = ann.get("ROLES", {})
    roles["subject"] = age_spec(ages.get("name1", "18+"))
    if "friend" in villagers:
        roles["friend"] = age_spec(ages.get("name2", "18+"))
    for letter, (rid, age) in figs.items():
        roles[rid] = age_spec(age)
    if "s" in marks_all:
        roles["other"] = {"kind": "stranger", "sex": "random"}
    multi = len(roles) > 1
    shown = {}
    for k, (s, marks) in texts.items():
        it = iter(marks)
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
        q = {"type": "question", **q,
             "choices": [{"label": shown[lk], "next": ok.lower(), "src": L(ev.parts[lk])}
                         for lk, ok in (("L1", "O1"), ("L2", "O2"))]}
        nodes = {"setup": q, "o1": page("O1", "Outcome A"), "o2": page("O2", "Outcome B")}
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
    if grammar:
        doc["grammar_fixes"] = grammar
    return doc, problems


def main() -> int:
    docs, problems = [], []
    only = sys.argv[1:]
    for sid, (_t, _n, sec, pre) in lib.DRAFTS_B.items():
        if only and pre.lower() not in only:
            continue
        anns = P.read_annotations(sid)
        for ev in P.events(sid):
            doc, probs = build(ev, anns.get(ev.code, {}))
            problems += probs
            docs.append((lib.DRAFTS_B_DIR / sec / f"{ev.row['id']}.json", doc))
    for p in problems:
        print("PROBLEM", p)
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    rc = subprocess.call([sys.executable, str(P.ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
