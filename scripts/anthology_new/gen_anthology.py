"""Write the owner's all-in-one Animals anthology's newest volumes (collection_lib.ANTHOLOGY) as collection events,
then format and check them:

    python scripts/anthology_new/gen_anthology.py [section ...]      # e.g. an_rel an_child
    python scripts/anthology_new/gen_anthology.py --sheet an_rel     # the review sheet: every page as shown

  MOM-01..08            Global Editorial Override (micro-event examples)           an_mom    (two choices)
  REL-01..36            Love by Choice, Coming Out, Names and Presentation          an_rel
  CHILD-01..47          Childhood Curiosity, Puppy Love and Questions               an_child
  FAM-01..24            Family Friction, Everyday Boundaries, Separation ...        an_fam
  JOY-01..38            Celebrations, Leisure, Remembrance and Body Art             an_joy
  EVENT-HS-001..042     The Human Spectrum, Island Comforts, Authority, Injury ...  an_hs
  EVENT-AGE-001..036    Every Age in the Limelight                                  an_age
  EVENT-JUSTICE-001..032  Justice, Bullying, Consequences, Trauma, Recovery ...     an_jus
  EVENT-EXPRESSION-001..074  Self-Expression, Art, Sport, Ecology, Governance ...   an_expr
  EVENT-FAUNA-001..024  Animals of Fur, Feathers, Scales, Claws and Hooves          an_fauna

THE SHAPE (the Living Event Engine's fixed volumes, scripts/living_vols/living_common.py): the setup is the question
page with the choice labels; each label leads to its OWN pair of outcomes, equally likely alternatives (a silent
branch, one page each).  "SETUP:", "A." and "A1." are structural markers; an "ELIGIBILITY:" line is the casting,
carried out as the roles' ages (a ledger note).  Each volume is one series.

THE AUTHORING RECORD (the owner and the lead, 2026-11-15):
- Text verbatim: minimal editing, no swaps, no rule-driven rewording.  Things need not exist in the game to appear in
  the text (worldbuilding).  Bad behaviour may be depicted; the narrative never endorses it.
- Names instead of vague roles: a person the text names by a role word ("a villager", "the friend", "a researcher")
  is a cast villager shown by name -- the role word becomes the name, and a job or description met with "a"/"an" keeps
  its word after the name ("Kai, a researcher, explains"); flavour only, the villager need not have the job.  Every
  such change is a ledger "sensitivity" entry.  Choice labels and titles keep their words.
- Chosen names (REL): the engine's new-name role (cie-v6-binary.md 28): a random first name from the game's own lists
  (and a last name with Last Names), shown in the story; nobody is renamed.
- Presentation: a real change of gender is the sex_change effect (code 22); a change of clothes or look that keeps
  the villager's identity needs the cross-sex look (code 23), not on this base: story text with a ledger TODO.
- Carrying or nursing parents are the game's nursing parent ("special": "nursing_parent", female, 18+); the engine
  cannot read a birth sex, so each such event carries a ledger TODO.
- Effects only where an outcome's own words make one: hair dye the villager keeps is the random new head look
  (MOM-06's "[hair color change]", REL-30); a cast villager who celebrates is celebrate.  Everything else -- injuries
  that are the event's premise, feelings, councils, customs, relationships -- is story text (text_only, a reason).
- Romance: teens only with teens at most two years apart; minor-adult never; adult couples at most 15 years apart.

THE ANNOTATIONS (scripts/anthology_new/annotations/<section>.txt, one block per event):
  REL-15
  R villager 18+ : villager | adult villager      a role: id, age ("18+", "3-13"; "/f" "/m" a sex; "/nursing" the
                                                   nursing parent), optional "@A1,C2" pages, then its phrases ("+"
                                                   keeps the word after the name, "-" replaces it)
  NEW chosen villager other                        a new-name role for villager (sex same / other / random)
  E S: "before" => "after"                         an exact edit of one page ([id] is a role's name)
  FX B1: sex villager                              an effect (sex, celebrate, look)
  GAP friend villager 2                            at most 2 years apart
  REL friend spouse_of villager                    a recorded relation
  TODO: presentation effect 23 pending             a ledger note on the heading
  DESC: ...                                        the Pick Island Event sentence (default: the setup)

Nothing here touches a game, a save or an exe.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402

ANN_DIR = Path(__file__).resolve().parent / "annotations"
SRC = lib.ANTHOLOGY_ID
CODE_OF = {"an_mom": "MOM", "an_rel": "REL", "an_child": "CHILD", "an_fam": "FAM", "an_joy": "JOY", "an_hs": "HS",
           "an_age": "AGE", "an_jus": "JUS", "an_expr": "EXP", "an_fauna": "FAU"}
# words met as a plain role: the name replaces them ("the villager" -> the name); any other role word met with
# "a"/"an" keeps its word after the name ("a researcher" -> "Kai, a researcher,")
PLAIN = {"villager", "child", "adult", "elder", "teen", "teenager", "friend", "companion", "partner", "toddler",
         "person", "grandparent", "sibling", "relative", "parent", "boy", "girl", "young adult"}
STORY_ONLY = "the volume's outcomes are story text unless an effect is marked"
WORD_WHY = {
    "food": "food in the story (a meal, a feast, fruit); the village's stores do not change -- " + STORY_ONLY,
    "tech": "technology talked about in the story; no tech points change -- " + STORY_ONLY,
    "skill": "\"skill\" in the everyday sense, not a skill gain -- " + STORY_ONLY,
    "celebrate": "a celebration talked about or planned in the story; nobody celebrates in the game -- " + STORY_ONLY,
    "health": "health or an injury in the story (the event's premise or a word in passing); nobody's health "
              "changes -- " + STORY_ONLY,
    "preference": "a feeling in the moment, not a lasting dislike -- " + STORY_ONLY,
    "kill": "a death only talked about (the premise or the word's everyday sense); nobody dies -- " + STORY_ONLY,
    "vanish": "the word's everyday sense (an animal, a sound, a thing or a mark out of sight); nobody leaves the "
              "village -- " + STORY_ONLY,
    "damage": "a thing breaks or collapses in the story; no building is damaged -- " + STORY_ONLY,
}
NAME_WHY = ("the owner (2026-11-15): names instead of vague roles -- the person the role word names is a cast villager "
            "shown by name (flavour only: the villager need not have that job)")
NEW_WHY = ("the lead (2026-11-15): a chosen name is the engine's new-name role (cie-v6-binary.md 28), shown in the "
           "story; nobody is renamed")
NURSING_TODO = ("TODO: a carrying or nursing parent must be born female; the engine reads only the sex field now "
                "(the role is the game's nursing parent, female), not a birth sex")
PRESENT_TODO = "TODO: presentation effect 23 pending (a cross-sex look that keeps the villager's identity)"


def L(n: int) -> str:
    return f"L{n}"


def raw(n: int) -> str:
    with lib.use_source(SRC):
        return lib.line(n)


def norm(n: int) -> str:
    return lib.normalize_source_text(raw(n))


BRACKET_RE = re.compile(r"\s*\[[^\]]+\]")


def shown(n: int, fixes: list[tuple[str, str]]) -> str:
    """Line n as its page shows it: the edits made, an "[instruction]" cut, the structural markers taken out."""
    cuts = [m.group(0).strip() for m in BRACKET_RE.finditer(norm(n))]
    with lib.use_source(SRC):
        p = cc.processed_line(n, {n: cuts} if cuts else {}, {n: fixes} if fixes else {})
    return p[:1].upper() + p[1:]


# ---- Rows and annotations ---------------------------------------------------------------------------------------------

def rows(section: str) -> list[dict]:
    data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
    return sorted((r for r in data["rows"] if r.get("source") == SRC and r["kind"] == "event"
                   and r["section"] == section), key=lambda r: r["lines"][0])


def code_of(row: dict) -> str:
    num = int(re.match(r"an[a-z]+?(\d+)_", row["id"]).group(1))
    pre = CODE_OF[row["section"]]
    return f"{pre}-{num:02d}" if pre in ("MOM", "REL", "CHILD", "FAM", "JOY") else f"{pre}-{num:03d}"


def read_annotations(section: str) -> dict[str, dict]:
    path = ANN_DIR / f"{section}.txt"
    out: dict[str, dict] = {}
    cur = None
    pre = CODE_OF[section]
    for s in path.read_text(encoding="utf-8").splitlines():
        s = s.rstrip()
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if re.fullmatch(rf"{pre}-\d+", s.strip()):
            cur = out.setdefault(s.strip(), {"roles": [], "edits": [], "fx": [], "new": [], "gap": [], "rel": [],
                                             "todo": []})
            continue
        if cur is None:
            raise SystemExit(f"{path.name}: line before any event: {s!r}")
        m = re.match(r"^R (\w+) (\S+)(?: @([A-D0-9S,]+))?\s*:\s*(.*)$", s)
        if m:
            rid, age, scope, phrases = m.groups()
            cur["roles"].append({"id": rid, "age": age, "scope": set(scope.split(",")) if scope else None,
                                 "phrases": [p.strip() for p in phrases.split("|") if p.strip()]})
            continue
        m = re.match(r'^E (S|[A-D]\d?): "(.*)" => "(.*)"$', s)
        if m:
            cur["edits"].append(m.groups())
            continue
        m = re.match(r"^FX ([A-D]\d): (\w+) (\w+)$", s)
        if m:
            cur["fx"].append(m.groups())
            continue
        m = re.match(r"^NEW (\w+) (\w+) (same|other|random)$", s)
        if m:
            cur["new"].append(m.groups())
            continue
        m = re.match(r"^GAP (\w+) (\w+) (\d+)$", s)
        if m:
            cur["gap"].append((m.group(1), m.group(2), int(m.group(3))))
            continue
        m = re.match(r"^REL (\w+) (\w+) (\w+)$", s)
        if m:
            cur["rel"].append(m.groups())
            continue
        m = re.match(r"^SAMESEX (\w+) (\w+)$", s)
        if m:
            cur["samesex"] = m.groups()
            continue
        m = re.match(r"^(DESC|TODO|REVIEW):\s*(.*)$", s)
        if m:
            if m.group(1) == "TODO":
                cur["todo"].append(m.group(2))
            else:
                cur[m.group(1)] = m.group(2)
            continue
        raise SystemExit(f"{path.name}: unreadable line {s!r}")
    return out


def age_spec(spec: str) -> dict:
    if spec == "stranger":                 # a named person from outside the village (cie-v6-binary.md 16)
        return {"kind": "stranger", "sex": "random", "named": True}
    sex = nursing = None
    parts = spec.split("/")
    for extra in parts[1:]:
        if extra == "nursing":
            nursing = True
        else:
            sex = {"f": "female", "m": "male"}[extra]
    a = parts[0]
    m = re.fullmatch(r"(\d+)\+", a)
    if m:
        out = {"kind": "villager", "min_age": int(m.group(1))}
    else:
        m = re.fullmatch(r"(\d+)-(\d+)", a)
        assert m, spec
        out = {"kind": "villager", "min_age": int(m.group(1)), "max_age": int(m.group(2))}
    if sex:
        out["sex"] = sex
    if nursing:
        out["special"] = "nursing_parent"
    return out


# ---- Names --------------------------------------------------------------------------------------------------------------

ART = r"(?P<art>A|An|a|an|The|the)"
AMBIGUOUS: list[str] = []          # a page where one role is named by two different words (two people?)


def name_pairs(text: str, part: str, roles: list[dict], keep: list[tuple[int, int]] = ()
               ) -> tuple[str, list[tuple[str, str]]]:
    """The page's line with each role word named: (the new line, the (before, after) pairs in order).  Text inside
    `keep` (an exact edit's words) is left alone."""
    phrases: dict[str, tuple[str, str]] = {}          # phrase -> (role id, mode "+" / "-")
    for r in roles:
        if r["scope"] is not None and part not in r["scope"]:
            continue
        for p in r["phrases"]:
            mode = p[-1] if p[-1] in "+-" else ("-" if p in PLAIN else "+")
            word = p.rstrip("+-").strip()
            phrases.setdefault(word, (r["id"], mode))
    if not phrases:
        return text, []
    alt = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    rx = re.compile(rf"(?<![\w(]){ART} (?P<ph>{alt})(?![\w-])")
    out, pairs, i = [], [], 0
    seen: dict[str, set[str]] = {}
    for m in rx.finditer(text):
        if any(a < m.end() and m.start() < b for a, b in keep):
            continue
        rid, mode = phrases[m.group("ph")]
        art = m.group("art")
        after_ch = text[m.end():m.end() + 1]
        if art.lower() == "the" or mode == "-":
            rep = f"({rid})"
        elif after_ch in ("'", "’"):
            continue                                    # "a teacher's reminder": not a person of the scene
        else:
            rep = f"({rid}), {art.lower()} {m.group('ph')}"
            if after_ch == " ":
                rep += ","
        out.append(text[i:m.start()])
        out.append(rep)
        pairs.append((m.group(0), rep))
        seen.setdefault(rid, set()).add(m.group("ph"))
        i = m.end()
    out.append(text[i:])
    for rid, phs in seen.items():
        if len(phs) > 1:
            AMBIGUOUS.append(f"{part}: role {rid} named by {sorted(phs)} on one page")
    return "".join(out), pairs


def fix_pairs(original: str, target: str, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Ledger pairs that make `target` from `original` the way the checker applies them (str.replace, in order);
    when the small pairs cannot, one pair over the changed span."""
    pairs = list(dict.fromkeys(pairs))
    s = original
    for b, a in pairs:
        s = s.replace(b, a)
    if s == target:
        return pairs
    i = 0
    while i < min(len(original), len(target)) and original[i] == target[i]:
        i += 1
    j = 0
    while j < min(len(original), len(target)) - i and original[-1 - j] == target[-1 - j]:
        j += 1
    while i > 0 and original[i - 1] != " ":
        i -= 1
    b, a = original[i:len(original) - j], target[i:len(target) - j]
    assert original.replace(b, a) == target, (original, target)
    return [(b, a)]


# ---- One event ------------------------------------------------------------------------------------------------------------

def kinds(effects: list[dict]) -> set[str]:
    return {cc.EFFECT_KIND.get(e["do"], e["do"]) for e in effects}


def text_only(lines: list[int], effects: list[dict]) -> list[dict]:
    have, out = kinds(effects), []
    text = " ".join(norm(n) for n in lines)
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


def effect(kind: str, rid: str) -> dict:
    if kind == "celebrate":
        return {"do": "celebrate", "who": rid}
    if kind == "look":
        return {"do": "appearance", "role": rid, "head": "random"}
    if kind == "sex":
        return {"do": "sex_change", "role": rid}
    raise SystemExit(f"unknown effect {kind!r}")


def build(row: dict, ann: dict) -> tuple[dict, list[str], list[str]]:
    code = code_of(row)
    problems: list[str] = []
    h, last = row["lines"]
    nc = row["choices"]
    letters = "abcd"[:nc]
    elig = raw(h + 1).startswith("ELIGIBILITY:")
    setup = h + 1 + elig
    assert norm(setup).startswith("SETUP:"), code
    parts = {"S": setup}
    for i, k in enumerate(letters):
        lab = setup + 1 + 3 * i
        assert re.match(rf"^\s*{k.upper()}\. ", raw(lab)), (code, k)
        parts[k.upper()] = lab
        for j in (1, 2):
            assert re.match(rf"^\s*{k.upper()}{j}\. ", raw(lab + j)), (code, k, j)
            parts[f"{k.upper()}{j}"] = lab + j
    assert max(parts.values()) == last, code
    roles_ann = ann.get("roles", [])
    role_ids = {r["id"] for r in roles_ann} | {n[0] for n in ann.get("new", [])}

    def tok(s: str) -> str:
        return re.sub(r"\[(\w+)\]", lambda m: f"({m.group(1)})", s)

    ledger: list[dict] = []
    if elig:
        ledger.append({"src": L(h + 1), "kind": "note",
                       "why": "the volume's casting tag (" + norm(h + 1)[len("ELIGIBILITY:"):].strip()
                              + "), carried out as the roles' ages"})
    for t in ann.get("todo", []):
        ledger.append({"src": L(h), "kind": "note", "why": t})
    if any(age_spec(r["age"]).get("special") == "nursing_parent" for r in roles_ann):
        ledger.append({"src": L(h), "kind": "note", "why": NURSING_TODO})
    texts: dict[str, str] = {}
    sens_count = 0
    for k, n in parts.items():
        for m in BRACKET_RE.finditer(norm(n)):
            ledger.append({"src": L(n), "kind": "instruction", "text": m.group(0).strip(),
                           "why": "the volume's effect, never shown: the outcome's effect"})
    for k, n in parts.items():
        original = norm(n)
        cur = original
        pairs: list[tuple[str, str]] = []
        for part, before, after in ann.get("edits", []):
            if part != k:
                continue
            if cur.count(before) != 1:
                problems.append(f"{code} {k}: edit before {before!r} occurs {cur.count(before)} times")
                continue
            cur = cur.replace(before, tok(after))
            pairs.append((before, tok(after)))
        keep = [(m.start(), m.end()) for _b, a in pairs for m in re.finditer(re.escape(a), cur)]
        if len(k) != 1 or k == "S":                       # pages, not labels
            cur2, more = name_pairs(cur, k, roles_ann, keep)
            cur = cur2
            pairs += more
        fixes = fix_pairs(original, cur, pairs) if cur != original else []
        for b, a in fixes:
            new_ids = {x[0] for x in ann.get("new", [])}
            why = NEW_WHY if set(re.findall(r"\((\w+)\)", a)) & new_ids else NAME_WHY
            ledger.append({"src": L(n), "kind": "sensitivity", "before": b, "after": a, "why": why})
            sens_count += 1
        t = shown(n, fixes)
        t = re.sub(r"\bchief(?=s?\b)", "{@chief}", t)
        t = re.sub(r"\bChief(?=s?\b)", "{@Chief}", t)
        texts[k] = t
    allowed = set(ann.get("REVIEW", "").split("ok-ambiguous:")[-1].split()) if "ok-ambiguous:" in ann.get(
        "REVIEW", "") else set()
    problems += [f"{code} {a}" for a in AMBIGUOUS if a.split(":")[0] not in allowed]
    AMBIGUOUS.clear()
    used_tokens = set(re.findall(r"\((\w+)\)", " ".join(texts.values())))
    unknown = used_tokens - role_ids
    if unknown:
        problems.append(f"{code}: tokens with no role {sorted(unknown)}")
    # roles
    roles: dict = {}
    for r in roles_ann:
        roles[r["id"]] = age_spec(r["age"])
    for rid, other, years in ann.get("gap", []):
        roles[rid]["max_age_gap"] = {"role": other, "years": years}
    for rid, kind, other in ann.get("rel", []):
        roles[rid]["relation"] = {kind: other}
    for rid, of, sex in ann.get("new", []):
        roles[rid] = {"kind": "stranger", "new_name_for": of, "sex": sex, "last_name": "same"}
    for rid in roles:
        if rid not in used_tokens and not any(f[2] == rid for f in ann.get("fx", [])):
            problems.append(f"{code}: role {rid} is never shown and has no effect")
    fx: dict[str, list[dict]] = {}
    for part, kind, rid in ann.get("fx", []):
        assert rid in roles, (code, rid)
        fx.setdefault(part.lower(), []).append(effect(kind, rid))
    chief = any("{@chief}" in t or "{@Chief}" in t for t in texts.values())

    def lab_text(k: str) -> str:
        t = lib.title_case_label(texts[k].rstrip().replace("{@chief}", "chief").replace("{@Chief}", "Chief"))
        return re.sub(r"\bChief(?=s?\b)", "{@Chief}", t)

    nodes: dict = {}
    choices = []
    for k in letters:
        K = k.upper()
        choices.append({"label": lab_text(K), "next": k, "src": L(parts[K])})
        kids = []
        for j in (1, 2):
            key = f"{k}{j}"
            n = parts[key.upper()]
            page = {"name": f"Outcome {key.upper()}", "text": texts[key.upper()], "src": L(n)}
            eff = fx.get(key, [])
            if eff:
                page["effects"] = [dict(e, src=L(n)) for e in eff]
            to = text_only([n], eff)
            if to:
                page["text_only"] = [dict(t, src=L(n)) for t in to]
            nodes[key] = page
            kids.append({"next": key})
        nodes[k] = {"type": "branch", "name": f"Answer {K}", "children": kids}
    q = {"type": "question", "name": "The setup", "text": texts["S"], "src": L(setup), "choices": choices}
    to = text_only([setup] + [parts[k.upper()] for k in letters], [])
    if to:
        q["text_only"] = [dict(t, src=L(setup)) for t in to]
    ordered = {"setup": q}
    for k in letters:
        ordered[k] = nodes[k]
        ordered[f"{k}1"] = nodes[f"{k}1"]
        ordered[f"{k}2"] = nodes[f"{k}2"]
    desc = ann.get("DESC")
    if not desc:
        desc = shown(setup, [])
        desc = desc.replace("’", "'")
    if not (cc.DESCRIPTION_RE.fullmatch(desc) and len(desc) <= cc.DESCRIPTION_MAX):
        problems.append(f"{code}: description needs a DESC ({len(desc)}): {desc!r}")
    used = {e.get("role") or e.get("who") for e in sum(fx.values(), [])}
    col = {"id": row["id"], "title_src": L(h), "ledger": ledger, "description": desc, "label_case": "title"}
    cast_only = [r for r, spec in roles.items() if spec["kind"] == "villager" and r not in used]
    if cast_only:
        col["cast_only"] = cast_only
    doc = {"format": "vvfp-cie-graph", "version": 6, "title": row["title"], "games": row["games"],
           "collection": col,
           "requirement": {"min_eligible": sum(1 for r in roles.values() if r["kind"] == "villager")},
           "roles": roles, "start": "setup", "nodes": ordered}
    if chief or "Chief" in row["title"]:
        doc["words"] = {"chief": {"3": "chief", "*": "leader"}, "Chief": {"3": "Chief", "*": "Leader"}}
        if "Chief" in row["title"]:
            doc["title_variants"] = [{"if": {"game": [g for g in row["games"] if g != 3]},
                                      "title": row["title"].replace("Chief", "Leader")}]
    if ann.get("samesex"):
        doc = same_sex_variants(doc, *ann["samesex"])
    return doc, problems, [code]


def same_sex_variants(doc: dict, a0: str, b0: str) -> dict:
    """The owner's rule for a same-sex couple whose sexes the text does not give (as BLF-36, scripts/drafts_c/
    gen_drafts_c.py same_sex_variants): the pair (a0, b0) becomes two men (men1, men2) and two women (women1,
    women2); the event starts with a branch of two equally likely children, each leading to its own copy of the
    pages.  The men are needed and the women optional (their child is taken only when both are cast), so where no
    two women can be cast the men's version shows."""
    import copy
    pairs = {"m": ("men1", "men2", "male"), "f": ("women1", "women2", "female")}
    base = {k: v for k, v in doc["roles"].items() if k not in (a0, b0)}
    spec = {k: v for k, v in doc["roles"][a0].items() if k not in ("sex", "max_age_gap")}
    gap = doc["roles"][b0].get("max_age_gap")
    roles = dict(base)
    for a, b, sex in pairs.values():
        opt = {"optional": True} if sex == "female" else {}
        roles[a] = dict(spec, sex=sex, **opt)
        roles[b] = dict(spec, sex=sex, **opt)
        if gap:
            roles[b]["max_age_gap"] = {"role": a, "years": gap["years"]}

    def swap(obj, a, b):
        s = json.dumps(obj, ensure_ascii=False)
        s = re.sub(rf"\({a0}([.)])", rf"({a}\1", s)
        s = re.sub(rf"\({b0}([.)])", rf"({b}\1", s)
        for key in ("who", "role"):
            s = s.replace(f'"{key}": "{a0}"', f'"{key}": "{a}"').replace(f'"{key}": "{b0}"', f'"{key}": "{b}"')
        return json.loads(s)

    nodes, children = {}, []
    for tag, (a, b, _sex) in pairs.items():
        for k, nd in doc["nodes"].items():
            nd = swap(copy.deepcopy(nd), a, b)
            for c in nd.get("choices", []) + nd.get("children", []):
                c["next"] = f"{c['next']}_{tag}"
            nodes[f"{k}_{tag}"] = nd
        children.append({"next": f"{doc['start']}_{tag}"} if tag == "m" else
                        {"next": f"{doc['start']}_{tag}", "if": {"all": [{"role": a}, {"role": b}]}})
    doc = dict(doc, roles=roles, start="pair", nodes={"pair": {"type": "branch", "name": "The couple",
                                                               "children": children}, **nodes})
    doc["requirement"] = {"min_eligible": sum(1 for r in base.values() if r["kind"] == "villager") + 2}
    col = dict(doc["collection"])
    used = {e.get("role") or e.get("who") for nd in nodes.values() for e in nd.get("effects", [])}
    col["cast_only"] = [r for r, v in roles.items() if v["kind"] == "villager" and r not in used]
    if not col["cast_only"]:
        col.pop("cast_only")
    col["ledger"] = col["ledger"] + [{"src": col["title_src"], "kind": "note",
                                      "why": "the owner's rule for a same-sex couple: cast by sex (two men or two "
                                             "women, equally likely where both can be cast), the relationship as "
                                             "story text"}]
    doc["collection"] = col
    return doc


def sheet(section: str) -> str:
    anns = read_annotations(section)
    out = []
    for row in rows(section):
        code = code_of(row)
        doc, probs, _ = build(row, anns.get(code, {}))
        roles = " ".join(f"{k}={v.get('min_age', '')}-{v.get('max_age', '')}{v.get('sex', '')[:1]}"
                         if v["kind"] == "villager" else f"{k}=new({v.get('new_name_for')})"
                         for k, v in doc["roles"].items())
        out.append(f"### {code} {row['title']} | {roles}")
        for p in probs:
            out.append(f"  !! {p}")
        nd = doc["nodes"]
        if "setup" not in nd:                                  # a same-sex couple's two versions: show the men's
            nd = {k[:-2]: v for k, v in nd.items() if k.endswith("_m")}
        out.append(f"  S: {nd['setup']['text']}")
        for c in nd["setup"]["choices"]:
            k = c["next"].removesuffix("_m")
            fx1 = [e["do"] for e in nd[k + '1'].get('effects', [])]
            fx2 = [e["do"] for e in nd[k + '2'].get('effects', [])]
            out.append(f"  {k.upper()}: {c['label']}")
            out.append(f"    1: {nd[k + '1']['text']}" + (f"  [{fx1}]" if fx1 else ""))
            out.append(f"    2: {nd[k + '2']['text']}" + (f"  [{fx2}]" if fx2 else ""))
    return "\n".join(out)


def main() -> int:
    args = sys.argv[1:]
    sys.stdout.reconfigure(encoding="utf-8")
    if args and args[0] == "--sheet":
        for sec in args[1:]:
            print(sheet(sec))
        return 0
    sections = args or list(lib.ANTHOLOGY_SECTIONS)
    docs, problems = [], []
    for sec in sections:
        anns = read_annotations(sec)
        seen = set()
        for row in rows(sec):
            code = code_of(row)
            seen.add(code)
            doc, probs, _ = build(row, anns.get(code, {}))
            problems += probs
            docs.append((lib.ANTHOLOGY_DIR / sec / f"{row['id']}.json", doc))
        extra = set(anns) - seen
        if extra:
            problems.append(f"{sec}: annotations for no event: {sorted(extra)}")
    for p in problems:
        print("PROBLEM", p)
    paths = []
    for p, doc in docs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(cc.canonical(cc.with_outcome_effects(doc, p)), encoding="utf-8", newline="\n")
        paths.append(str(p))
    rc = subprocess.call([sys.executable, str(ROOT / "scripts" / "collection_check.py"), "--format", *paths])
    return rc or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
